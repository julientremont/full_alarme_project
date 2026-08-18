"""
alarm.py — Orchestrateur alarme AEGIS (multi-caméras).

Principe de conception (audit 2026-07-09, cf. docs/10) :
  Le thread réseau MQTT ne fait JAMAIS d'I/O caméra ni de notification bloquante.
  Il mute l'état sous verrou, publie l'état tout de suite, puis délègue le lent
  (sirène, privacy, mail/Telegram) à un pool de workers. Conséquence :
    - le DÉSARMEMENT est traité et publié instantanément, jamais bloqué ;
    - l'ALERTE part avant les sirènes (reçue en < 1 s) ;
    - une caméra Tapo lente/suspendue ne retarde plus rien.

Armé :
  - Veille : chaque caméra compare 2 images toutes les 2 s ; si mouvement -> YOLO.
  - Capteur d'ouverture -> YOLO direct sur la caméra de la pièce (mapping par pièce).
  - Porte d'entrée : tempo (ENTRY_DELAY_S) avant déclenchement (le temps de désarmer).
Alarme (personne détectée / ouverture hors entrée) :
  - Alerte (mail + Telegram) envoyée EN PREMIER, en asynchrone.
  - Sirène externe (Zigbee/Tuya via MQTT) déclenchée immédiatement ; sirènes
    caméra tentées en parallèle (best-effort, souvent non supportées C210).
  - Photos de TOUTES les caméras toutes les ALARM_PHOTO_S s (sauvegarde même
    sans détection YOLO, annotée si objet trouvé).
  - Arrêt UNIQUEMENT au désarmement manuel via l'app.

MQTT : voir docs/05. Bus Mosquitto.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import paho.mqtt.client as mqtt
import yaml
from dotenv import load_dotenv

import notify
from camera import Camera

for vault in ("/home/j.tremont/.secrets/vault.env",
              os.path.join(os.path.dirname(__file__), ".env")):
    if os.path.exists(vault):
        load_dotenv(vault)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("aegis.orch")

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
Z2M_BASE = os.getenv("MQTT_BASE_TOPIC", "zigbee2mqtt")
MOTION_GAP = float(os.getenv("MOTION_GAP_S", "1"))
CAPTURE_MIN_INTERVAL = float(os.getenv("CAPTURE_MIN_INTERVAL_S", "5"))  # 1 photo max / caméra / Xs
ENTRY_DELAY_S = int(os.getenv("ENTRY_DELAY_S", "30"))     # tempo au retour (temps de désarmer)
EXIT_DELAY_S = int(os.getenv("EXIT_DELAY_S", "60"))       # délai de sortie (temps de sortir après armement)
ENTRY_SENSORS = set(os.getenv("ENTRY_SENSORS", "porte_entree").split(","))
# Mode privé caméras (masquées quand désarmé). Désactivé par défaut : les C210
# se bloquent à force de basculer -> caméras noires. Sans, elles sont toujours
# dispo et visibles (elles ne capturent que pendant une alarme de toute façon).
PRIVACY_MODE = os.getenv("CAMERA_PRIVACY", "0").lower() in ("1", "true", "yes")

# Sirène externe (matérielle) pilotée par MQTT. Renseigner SIREN_SET_TOPIC pour
# activer (ex: une sirène Zigbee exposée par Z2M -> "zigbee2mqtt/sirene/set").
# Par défaut ON/OFF suivent le format "warning" Zigbee (IAS WD).
# Messagerie déportée : depuis le 18/08/2026 c'est le service `aegis-notifier`
# qui envoie mail/Telegram (il recharge le vault à chaque démarrage, alors que
# ce process garde en mémoire l'environnement de SON lancement — cause de
# plusieurs semaines d'alertes muettes). Mettre à 1 pour revenir à l'envoi local.
ORCH_NOTIFY = os.getenv("AEGIS_ORCH_NOTIFY", "0").lower() in ("1", "true", "yes")

SIREN_TOPIC = os.getenv("SIREN_SET_TOPIC", "")
SIREN_ON_PAYLOAD = os.getenv(
    "SIREN_ON_PAYLOAD",
    '{"warning":{"mode":"emergency","level":"very_high","strobe":true,"strobe_duty_cycle":10,"strobe_level":"very_high","duration":900}}')
SIREN_OFF_PAYLOAD = os.getenv(
    "SIREN_OFF_PAYLOAD", '{"warning":{"mode":"stop","level":"low","strobe":false,"duration":0}}')

T_SET, T_STATE, T_EVENT, T_CAMERA = (
    "aegis/alarm/set", "aegis/alarm/state", "aegis/alarm/event", "aegis/camera/state")
T_DETECT = "aegis/detection/config"     # réglages YOLO diffusés par l'app (retenu)

DEVICES_YAML = os.path.join(os.path.dirname(__file__), "..", "webapp", "devices.yaml")


def _registry():
    return yaml.safe_load(open(DEVICES_YAML))["groups"]


def _build_cameras():
    # Contrôle pytapo (privacy/sirène) = auth LOCALE directe : user "admin" +
    # mot de passe du compte cloud, SANS cloudPassword. Aucun round-trip TP-Link
    # -> pas de « Temporary Suspension ». (Le mot de passe RTSP ne marche pas pour
    #  le contrôle ; c'est bien le mot de passe du compte cloud qu'il faut.)
    # RTSP (détection) = compte local de la caméra, via go2rtc.
    creds = dict(ctrl_user=os.getenv("TAPO_CTRL_USER", "admin"),
                 ctrl_password=(os.getenv("TAPO_CTRL_PASSWORD") or os.getenv("TAPO_CLOUD_PASSWORD")
                                or os.getenv("TAPO_PASSWORD")),
                 rtsp_user=os.getenv("TAPO_LOCAL_USER"), rtsp_password=os.getenv("TAPO_LOCAL_PASSWORD"),
                 stream=os.getenv("TAPO_STREAM", "stream1"))
    cams = {}
    for g in _registry():
        if g["id"] != "cameras":
            continue
        for d in g["devices"]:
            if d.get("real") and d.get("host"):
                c = dict(creds)
                # overrides par caméra (devices.yaml) si besoin
                if d.get("rtsp_user"):
                    c["rtsp_user"] = d["rtsp_user"]
                if d.get("rtsp_password"):
                    c["rtsp_password"] = d["rtsp_password"]
                if d.get("ctrl_user"):
                    c["ctrl_user"] = d["ctrl_user"]
                if d.get("ctrl_password"):
                    c["ctrl_password"] = d["ctrl_password"]
                cams[d["key"]] = Camera(key=d["key"], label=d.get("label", d["key"]),
                                        room=d.get("room", ""), host=d["host"],
                                        onboard_siren=d.get("onboard_siren", True), **c)
    return cams


def _sensor_maps(cameras):
    labels, sensor_cam = {}, {}
    room_to_cam = {c.room: c for c in cameras.values() if c.room}
    for g in _registry():
        for d in g.get("devices", []):
            labels[d["key"]] = d.get("label", d["key"])
            if d.get("source") == "zigbee" and d.get("kind") == "contact":
                cam = room_to_cam.get(d.get("room"))
                if cam:
                    sensor_cam[d["key"]] = cam
    return labels, sensor_cam


class Orchestrator:
    def __init__(self):
        self.lock = threading.Lock()
        self.armed = False
        self.alarm_active = False
        self.detection_enabled = True         # surveillance IA (pilotée par l'app)
        self.trigger_cam: Camera | None = None
        self.since = time.time()
        self._exit_until = 0.0                # fin du délai de sortie (zone entrée neutralisée)
        self._booting = True                  # fenêtre de démarrage : pas de notif arm/disarm (état retenu)
        self._got_command = False
        self._gen = 0                         # invalide les threads de veille au désarmement
        self._contact_cache: dict[str, bool] = {}
        self._entry_timers: dict[str, threading.Timer] = {}
        self._last_capture: dict[str, float] = {}   # cadence photo par caméra
        # Pool d'I/O : sirène/privacy/notif hors du thread réseau MQTT.
        self.pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="aegis-io")
        # File des messages MQTT (le thread réseau ne fait QUE parser + enfiler ;
        # tout traitement lent est déporté → le keepalive n'est jamais bloqué).
        self._inbox: queue.Queue = queue.Queue()
        self._connected = False
        self._mqtt_down_since = 0.0

        self.cameras = _build_cameras()
        self.sensor_labels, self.sensor_cam = _sensor_maps(self.cameras)
        # Alimentation caméras par prise Tapo (confidentialité physique) : map
        # caméra -> prise. Désarmé = prise coupée = caméra hors tension.
        self._cam_plug: dict[str, str] = {}
        for g in _registry():
            for d in g.get("devices", []):
                if d.get("source") == "camera" and d.get("power_plug"):
                    self._cam_plug[d["key"]] = d["power_plug"]
        self._power_plugs = bool(self._cam_plug)
        # Zone temporisée : une caméra est « entrée » si sa pièce est celle d'un
        # capteur d'entrée (porte_entree). Elle suit le délai sortie/entrée et
        # n'utilise pas la sirène embarquée (on doit pouvoir désarmer au retour).
        entry_rooms = set()
        for g in _registry():
            for d in g.get("devices", []):
                if d.get("key") in ENTRY_SENSORS and d.get("room"):
                    entry_rooms.add(d["room"])
        for cam in self.cameras.values():
            if cam.room in entry_rooms:
                cam.entry_zone = True
                cam.onboard_siren = False
        log.info("Caméras réelles : %s", [c.label for c in self.cameras.values()] or "aucune")
        log.info("Zone entrée (temporisée) : %s | sortie %ds / entrée %ds",
                 [c.label for c in self.cameras.values() if c.entry_zone], EXIT_DELAY_S, ENTRY_DELAY_S)
        log.info("Sirène externe MQTT : %s", SIREN_TOPIC or "(non configurée)")

        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                  client_id="aegis-orchestrator")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    # ─── helpers asynchrones (jamais sur le thread MQTT) ─────────────────────
    def _notify_async(self, title, line, key, force=True):
        if not ORCH_NOTIFY:
            return              # envoi assuré par aegis-notifier (évite le doublon)
        self.pool.submit(notify.send_alert, title, line, key=key, force=force)

    def _cam_call(self, cam: Camera, fn_name: str, args=(), gen: int | None = None):
        """Appel caméra dans un worker. Ignore si la génération a changé
        (désarmement survenu entre-temps) — évite de rallumer une sirène coupée."""
        if gen is not None and gen != self._gen:
            return
        try:
            getattr(cam, fn_name)(*args)
        except Exception as e:
            log.error("%s() %s : %s", fn_name, cam.label, str(e)[:120])

    def _ext_siren(self, on: bool):
        """Sirène matérielle via MQTT (publish instantané, non bloquant)."""
        if not SIREN_TOPIC:
            return
        self.client.publish(SIREN_TOPIC, SIREN_ON_PAYLOAD if on else SIREN_OFF_PAYLOAD)
        log.warning("Sirène externe %s (%s)", "ON" if on else "OFF", SIREN_TOPIC)

    def _set_cameras_power(self, on: bool):
        """Allume/coupe l'alimentation des caméras via leurs prises Tapo.
        Coupé (désarmé) = caméras hors tension = vraie confidentialité à la maison ;
        allumé (armé) = caméras sous tension (démarrage ~30-60 s)."""
        for plug in set(self._cam_plug.values()):
            self.client.publish(f"aegis/plug/{plug}/set", json.dumps({"on": bool(on)}))
        if self._cam_plug:
            log.warning("Alimentation caméras %s (prises Tapo)", "ON" if on else "OFF")

    # ─── MQTT ──────────────────────────────────────────────────────────────
    def _on_connect(self, c, u, f, rc, props=None):
        self._connected = True
        self._mqtt_down_since = 0.0
        log.info("MQTT connecté (rc=%s)", rc)
        c.subscribe(T_SET)
        c.subscribe(T_DETECT)                # réglages détection (retenu)
        c.subscribe(f"{Z2M_BASE}/+")
        c.subscribe("aegis/notify")          # demandes de notif d'autres composants (app)

    def _on_disconnect(self, c, u, *args):
        self._connected = False
        self._mqtt_down_since = time.time()
        log.warning("MQTT déconnecté — reconnexion automatique en cours")

    def _on_message(self, c, u, msg):
        """Thread réseau paho : parse + enfile UNIQUEMENT. Le désarmement (T_SET)
        est traité tout de suite car il est critique ET non bloquant ; tout le
        reste part dans la file (un handler lent ne doit jamais figer le keepalive
        et provoquer une déconnexion → c'était la cause du désarmement bloqué)."""
        try:
            payload = msg.payload.decode("utf-8", "replace")
        except Exception:
            return
        if msg.topic == T_SET:
            self._handle_set(payload)        # arm/désarm : prioritaire, immédiat
        else:
            self._inbox.put((msg.topic, payload))

    def _dispatch_loop(self):
        """Traite la file des messages MQTT hors du thread réseau."""
        while True:
            topic, payload = self._inbox.get()
            try:
                if topic == T_DETECT:
                    self._handle_detection(payload)
                elif topic == "aegis/notify":
                    self._handle_notify(payload)
                elif topic.startswith(f"{Z2M_BASE}/"):
                    self._handle_zigbee(topic, payload)
            except Exception as e:
                log.error("dispatch %s : %s", topic, str(e)[:120])

    def _mqtt_watchdog(self):
        """Filet de sécurité : si MQTT reste injoignable trop longtemps (thread
        réseau réellement figé), on force la sortie → systemd (Restart=always)
        relance un process sain qui reçoit l'état retenu (désarmement inclus)."""
        while True:
            time.sleep(15)
            if not self._connected and self._mqtt_down_since:
                down = time.time() - self._mqtt_down_since
                if down > 150:
                    log.critical("MQTT injoignable depuis %.0fs — redémarrage forcé", down)
                    os._exit(1)

    def _handle_notify(self, payload):
        try:
            d = json.loads(payload)
        except Exception:
            return
        title = d.get("title")
        line = d.get("line", "")
        if title:
            self._notify_async(title, line, d.get("key", title), force=bool(d.get("force", True)))

    def _handle_set(self, payload):
        try:
            data = json.loads(payload)
        except Exception:
            return
        self._got_command = True
        if data.get("state") == "armed":
            self.arm(data.get("by", "?"))
        elif data.get("state") == "disarmed":
            self.disarm(data.get("by", "?"))

    def _handle_detection(self, payload):
        """Applique les réglages YOLO diffusés par l'app (objets, confiance,
        sensibilité mouvement, activation de la surveillance IA)."""
        try:
            d = json.loads(payload)
        except Exception:
            return
        if not isinstance(d, dict):
            return
        if "enabled" in d:
            self.detection_enabled = bool(d["enabled"])
        classes = d.get("classes")
        conf = d.get("confidence")
        motion_seuil = d.get("motion_sensitivity")
        for cam in self.cameras.values():
            cam.apply_detection_config(
                classes=classes if isinstance(classes, list) else None,
                conf=conf, motion_seuil=motion_seuil)
        log.info("Réglages détection appliqués : IA=%s conf=%s seuil=%s classes=%s",
                 self.detection_enabled, conf, motion_seuil, classes)

    def _handle_zigbee(self, topic, payload):
        name = topic[len(Z2M_BASE) + 1:]
        if "/" in name or name.startswith("bridge"):
            return
        try:
            data = json.loads(payload)
        except Exception:
            return
        if not isinstance(data, dict) or "contact" not in data:
            return
        closed = bool(data["contact"])
        prev = self._contact_cache.get(name)
        self._contact_cache[name] = closed
        if prev and not closed:               # front d'ouverture uniquement
            with self.lock:
                armed, alarm = self.armed, self.alarm_active
            if armed and not alarm:
                self._on_open(name)

    # ─── transitions armé/désarmé ────────────────────────────────────────────
    def arm(self, by="?"):
        with self.lock:
            if self.armed:
                return
            self.armed = True
            self.alarm_active = False
            self.since = time.time()
            self._exit_until = time.time() + EXIT_DELAY_S  # fenêtre de sortie
            self._gen += 1
            gen = self._gen
        self.publish_state()                              # UI armée tout de suite
        self.publish_event("armed", "Alarme armée",
                           f"par {by} — sortie {EXIT_DELAY_S}s")
        if not self._booting:                             # au démarrage : notif consolidée par run()
            self._notify_async("Alarme armée",
                               f"Armée par {by}. Délai de sortie {EXIT_DELAY_S}s.", "armed")
        log.info("ALARME ARMÉE (par %s) — délai de sortie %ds", by, EXIT_DELAY_S)

        if self._power_plugs:
            self._set_cameras_power(True)                  # allume les caméras (elles démarrent)

        def _prep():                                       # privacy OFF + sirène embarquée
            for cam in self.cameras.values():
                if gen != self._gen:
                    return
                if self._power_plugs:
                    # Alimentées par prise : pas de privacy logiciel ni d'onboard
                    # (la caméra démarre). Elle deviendra joignable en ~30-60 s.
                    self.publish_camera(cam, reachable=True, privacy=False)
                    continue
                if cam.entry_zone and PRIVACY_MODE:         # entrée masquée pendant la sortie (si privé)
                    self.publish_camera(cam, reachable=True, privacy=True)
                    continue
                cam.set_privacy(False)
                cam.set_onboard_alarm(True)                # sonne sur détection caméra
                self.publish_camera(cam, reachable=True, privacy=False)
        self.pool.submit(_prep)

        def _activate_entry():                             # fin du délai de sortie
            if gen != self._gen:
                return
            for cam in self.cameras.values():
                if cam.entry_zone:
                    cam.set_privacy(False)
                    self.publish_camera(cam, reachable=True, privacy=False)
            log.info("Délai de sortie écoulé — zone entrée armée")
        if any(c.entry_zone for c in self.cameras.values()):
            t = threading.Timer(EXIT_DELAY_S, _activate_entry)
            t.daemon = True
            with self.lock:
                self._entry_timers["__exit__"] = t
            t.start()

        for cam in self.cameras.values():
            threading.Thread(target=self._veille, args=(cam, gen), daemon=True).start()

    def disarm(self, by="?"):
        with self.lock:
            was_armed = self.armed
            was_alarm = self.alarm_active
            self.armed = False
            self.alarm_active = False
            self.trigger_cam = None
            self._exit_until = 0.0
            self._gen += 1
            timers = list(self._entry_timers.values())
            self._entry_timers.clear()
        for t in timers:
            t.cancel()
        # Priorité absolue : couper la sirène réelle et publier l'état MAINTENANT.
        self._ext_siren(False)
        self.publish_state()
        if was_armed:
            self.publish_event("disarmed", "Alarme désarmée", f"par {by}")
            if not self._booting:
                self._notify_async("Alarme désarmée", f"L'alarme a été désarmée par {by}.", "disarmed")
            log.info("ALARME DÉSARMÉE (par %s)", by)

        if self._power_plugs:
            self._set_cameras_power(False)                 # coupe l'alim caméras = confidentialité

        def _shutdown():                                   # coupe sirènes (+ privacy si activé)
            for cam in self.cameras.values():
                if self._power_plugs:
                    # caméra mise hors tension par la prise → juste refléter l'état
                    self.publish_camera(cam, reachable=False, privacy=True)
                    continue
                cam.set_onboard_alarm(False)               # coupe la sirène embarquée
                if was_alarm:
                    cam.stop_siren()
                if PRIVACY_MODE:
                    cam.set_privacy(True)                  # re-masque seulement si mode privé
                self.publish_camera(cam, reachable=True, privacy=PRIVACY_MODE)
        self.pool.submit(_shutdown)

    # ─── veille (1 thread par caméra) ────────────────────────────────────────
    def _veille(self, cam: Camera, gen: int):
        log.info("Veille démarrée sur %s", cam.label)
        while True:
            with self.lock:
                if gen != self._gen or not self.armed:
                    return
                if not self.detection_enabled:      # surveillance IA désactivée depuis l'app
                    time.sleep(2)
                    continue
            moved, frame = cam.motion(MOTION_GAP)
            with self.lock:
                if gen != self._gen or not self.armed:
                    continue
                active = self.alarm_active
            if not moved:
                continue
            # Mouvement → YOLO. On sauve une photo AVEC cadre vert UNIQUEMENT si une
            # personne/objet est détecté (rien si pièce vide / vent), et au plus une
            # toutes les CAPTURE_MIN_INTERVAL s PAR CAMÉRA (cadence). Tourne aussi
            # pendant l'alarme : captures par caméra, seulement tant que quelqu'un
            # est visible, indépendamment sur chaque caméra.
            now = time.time()
            allow_save = (now - self._last_capture.get(cam.key, 0.0)) >= CAPTURE_MIN_INTERVAL
            detected = cam.detect(frame, save=allow_save)
            if detected and allow_save:
                self._last_capture[cam.key] = now
            if detected and not active:
                self._camera_trigger(cam, "Personne détectée", f"caméra {cam.label}")

    def _in_exit_window(self) -> bool:
        with self.lock:
            return time.time() < self._exit_until

    # ─── détection caméra (routée selon zone) ────────────────────────────────
    def _camera_trigger(self, cam: Camera, label, detail):
        """Détection YOLO. Zone entrée = tempo de retour (temps de désarmer) ;
        ailleurs = alarme immédiate."""
        if cam.entry_zone:
            if self._in_exit_window():
                return                                     # on sort encore : on ignore
            key = f"cam:{cam.key}"
            with self.lock:
                if key in self._entry_timers or not self.armed or self.alarm_active:
                    return                                 # tempo déjà en cours
            log.warning("Présence ENTRÉE (%s) — tempo %ds avant alarme", cam.label, ENTRY_DELAY_S)
            self.publish_event("door", "Présence entrée", f"{cam.label} — tempo {ENTRY_DELAY_S}s")
            t = threading.Timer(ENTRY_DELAY_S, self._entry_fire, args=(key, label, cam))
            t.daemon = True
            with self.lock:
                self._entry_timers[key] = t
            t.start()
        else:
            self.trigger_alarm(cam, label, detail)

    # ─── ouverture capteur ───────────────────────────────────────────────────
    def _on_open(self, sensor):
        label = self.sensor_labels.get(sensor, sensor.replace("_", " ").title())
        cam = self.sensor_cam.get(sensor) or self.trigger_cam or next(iter(self.cameras.values()), None)
        if sensor in ENTRY_SENSORS:
            if self._in_exit_window():
                log.info("Ouverture entrée %s pendant le délai de sortie — ignorée", label)
                return
            log.warning("Ouverture ENTRÉE %s — tempo %ds avant alarme", label, ENTRY_DELAY_S)
            self.publish_event("door", "Entrée ouverte", f"{label} — tempo {ENTRY_DELAY_S}s")
            t = threading.Timer(ENTRY_DELAY_S, self._entry_fire, args=(sensor, label, cam))
            t.daemon = True
            with self.lock:
                self._entry_timers[sensor] = t
            t.start()
        else:
            self.trigger_alarm(cam, "Ouverture détectée", label)

    def _entry_fire(self, sensor, label, cam):
        with self.lock:
            self._entry_timers.pop(sensor, None)
            if not self.armed or self.alarm_active:
                return
        log.warning("Tempo entrée écoulée sans désarmement → alarme")
        self.trigger_alarm(cam, "Intrusion (entrée)", label)

    # ─── alarme ──────────────────────────────────────────────────────────────
    def trigger_alarm(self, cam: Camera | None, label, detail):
        with self.lock:
            if not self.armed or self.alarm_active:
                return
            self.alarm_active = True
            self.trigger_cam = cam
            gen = self._gen
        log.warning("🚨 ALARME : %s (%s)", label, detail)
        # 1) ALERTER D'ABORD (asynchrone) — l'utilisateur est prévenu en < 1 s.
        self.publish_state()
        self.publish_event("intrusion", label, detail)
        self._notify_async("Alerte intrusion", f"{label} — {detail}.", "intrusion")
        # 2) Sirène externe matérielle immédiate.
        self._ext_siren(True)
        # 3) Sirènes caméra : best-effort, en parallèle, jamais bloquant.
        for c in self.cameras.values():
            self.pool.submit(self._cam_call, c, "start_siren", (), gen)
        # 4) Les photos (cadre vert, par caméra, seulement quand quelqu'un est
        #    visible) sont prises par la veille qui continue de tourner pendant
        #    l'alarme — pas de capture à l'aveugle qui saturait le Pi.

    # ─── publications ─────────────────────────────────────────────────────────
    def publish_state(self):
        with self.lock:
            mode = "alarm" if self.alarm_active else "idle"
            payload = {"state": "armed" if self.armed else "disarmed",
                       "mode": mode, "since": self.since}
        self.client.publish(T_STATE, json.dumps(payload), retain=True)

    def publish_event(self, etype, label, detail=""):
        self.client.publish(T_EVENT, json.dumps(
            {"type": etype, "label": label, "detail": detail, "ts": time.time()}))

    def publish_camera(self, cam: Camera, reachable: bool, privacy: bool):
        self.client.publish(f"aegis/camera/{cam.key}/state", json.dumps(
            {"key": cam.key, "label": cam.label, "reachable": bool(reachable),
             "privacy": bool(privacy), "ts": time.time()}), retain=True)

    # ─── run ──────────────────────────────────────────────────────────────────
    def run(self):
        threading.Thread(target=self._dispatch_loop, daemon=True).start()
        threading.Thread(target=self._mqtt_watchdog, daemon=True).start()
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)
        self.client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
        self.client.loop_start()
        log.info("Orchestrateur AEGIS démarré (%d caméra(s))", len(self.cameras))
        time.sleep(5)                          # laisser arriver l'état retenu (reprise armé/désarmé)
        self._booting = False                  # fin de la fenêtre de démarrage
        if not self._got_command:
            log.info("Aucune commande retenue — démarrage désarmé")
            self._ext_siren(False)
            self.publish_state()
        if self._power_plugs:
            # Alim caméras selon l'état repris : armé = allumées, désarmé = coupées.
            self._set_cameras_power(self.armed)
            for cam in self.cameras.values():
                self.publish_camera(cam, reachable=self.armed, privacy=not self.armed)
        elif not PRIVACY_MODE:                             # sinon, garantit les caméras visibles
            for cam in self.cameras.values():
                cam.set_privacy(False)
                self.publish_camera(cam, reachable=True, privacy=False)
        # Tout redémarrage est notifié (un intrus pourrait couper puis rétablir le
        # courant). L'état armé est repris depuis l'état MQTT retenu.
        etat = "ARMÉE" if self.armed else "désarmée"
        self.publish_event("system", "Redémarrage orchestrateur", f"alarme {etat}")
        self._notify_async("AEGIS redémarré", f"Orchestrateur relancé — alarme {etat}.", "boot")
        log.warning("Démarrage terminé — alarme %s", etat)
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    Orchestrator().run()
