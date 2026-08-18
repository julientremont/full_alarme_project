"""
notifier.py — Service de messagerie AEGIS (canal unique vers l'utilisateur).

Pourquoi ce service existe (18/08/2026) : l'orchestrateur charge le vault au
démarrage. Le vault ayant été enrichi APRÈS son lancement, ses identifiants
mail/Telegram étaient périmés et `notify` sortait en silence (`return` sans log).
Résultat : plus aucune alerte depuis des semaines, sans le moindre signe.

Ce service découple la messagerie de l'alarme : il ne fait que LIRE le bus MQTT,
donc il peut être redémarré à volonté sans jamais interrompre la surveillance.

Il envoie :
  1. chaque événement (armement, désarmement, ouverture, intrusion) en direct ;
  2. pendant une intrusion, un RAPPEL toutes les REPEAT_S secondes tant que
     l'alarme n'est pas désarmée (récap : déclencheur, caméras, durée) ;
  3. un RÉCAPITULATIF quotidien de l'état de tout le matériel ;
  4. une ALERTE IMMÉDIATE dès qu'un équipement tombe, avec l'heure exacte ;
     l'anomalie est mémorisée et rappelée dans le récap tant qu'elle dure.

MQTT (lecture seule) : aegis/alarm/state, aegis/alarm/event, aegis/plug/+/state,
aegis/camera/+/state, aegis/sensor/sirene/state, zigbee2mqtt/+, .../bridge/state
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt
import yaml
from dotenv import load_dotenv

# Le vault est rechargé À CHAQUE démarrage de ce service : c'est précisément
# l'absence de rechargement qui avait rendu l'orchestrateur muet.
for _v in ("/home/j.tremont/.secrets/vault.env",
           os.path.join(os.path.dirname(__file__), ".env")):
    if os.path.exists(_v):
        load_dotenv(_v, override=True)

import notify  # noqa: E402  (doit être importé APRÈS le chargement du vault)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("aegis.notifier")

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
Z2M = os.getenv("MQTT_BASE_TOPIC", "zigbee2mqtt")
GO2RTC_API = os.getenv("GO2RTC_API", "http://127.0.0.1:1984")
CAPTURES_DIR = os.getenv("CAPTURES_DIR", os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "webapp", "captures")))

REPEAT_S = int(os.getenv("NOTIFIER_REPEAT_S", "120"))        # rappel pendant intrusion
DAILY_AT = os.getenv("NOTIFIER_DAILY_AT", "08:00")           # heure du récap
HEALTH_EVERY_S = int(os.getenv("NOTIFIER_HEALTH_EVERY_S", "60"))
SENSOR_MUTE_H = int(os.getenv("NOTIFIER_SENSOR_MUTE_H", "6"))    # capteur sans nouvelle
NODE_TIMEOUT_S = int(os.getenv("NOTIFIER_NODE_TIMEOUT_S", "300"))  # routeurs/prises
STATE_FILE = os.path.join(os.path.dirname(__file__), ".notifier_state.json")
DEVICES_YAML = os.path.join(os.path.dirname(__file__), "..", "webapp", "devices.yaml")
FR = {"armed": "ARMÉE", "disarmed": "DÉSARMÉE"}


def _registry():
    with open(DEVICES_YAML) as f:
        return yaml.safe_load(f)["groups"]


def _labels() -> dict:
    out = {}
    for g in _registry():
        for d in g.get("devices", []):
            out[d["key"]] = d.get("label", d["key"])
    return out


def _hhmm(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def _since(ts: float) -> str:
    """Durée écoulée en clair : « 3 min », « 2 h 05 », « 4 j »."""
    s = max(0, int(time.time() - ts))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    if s < 86400:
        return f"{s // 3600} h {(s % 3600) // 60:02d}"
    return f"{s // 86400} j"


def _cams_detecting(since: float) -> list[str]:
    """Caméras ayant réellement produit une capture depuis `since`.

    Déduit des fichiers écrits par l'orchestrateur (« <Label>_<Objet>_<date>.jpg »)
    plutôt que d'un état interne : c'est la trace de ce qui a vraiment été vu.
    """
    out = []
    try:
        for f in os.listdir(CAPTURES_DIR):
            if not f.lower().endswith(".jpg"):
                continue
            if os.path.getmtime(os.path.join(CAPTURES_DIR, f)) >= since:
                cam = f.split("_", 1)[0]
                if cam and cam not in out:
                    out.append(cam)
    except Exception:
        pass
    return out


class Notifier:
    def __init__(self):
        self.lock = threading.Lock()
        self.labels = _labels()
        self.alarm = {"state": "unknown", "mode": "idle"}
        self.z2m: dict[str, dict] = {}        # friendly_name -> payload
        self.seen: dict[str, float] = {}      # friendly_name -> dernier message
        self.contact_change: dict[str, float] = {}  # dernier changement ouvert/fermé
        self.plugs: dict[str, dict] = {}
        self.sirene: dict = {}
        self.bridge_online = False
        # Intrusion en cours
        self.alarm_since = 0.0
        self.alarm_trigger = ""
        self.alarm_cams: list[str] = []
        self.alarm_repeats = 0
        # Anomalies : clé -> {"since": ts, "text": str}
        self.faults: dict[str, dict] = {}
        self.started = time.time()
        self._load()
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                  client_id="aegis-notifier")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # ─── persistance (les anomalies survivent à un redémarrage) ──────────────
    def _load(self):
        try:
            with open(STATE_FILE) as f:
                d = json.load(f)
            self.faults = d.get("faults", {})
            self.last_daily = d.get("last_daily", "")
        except Exception:
            self.last_daily = ""

    def _save(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"faults": self.faults, "last_daily": self.last_daily}, f)
        except Exception as e:
            log.warning("sauvegarde état : %s", e)

    # ─── envoi ───────────────────────────────────────────────────────────────
    def send(self, title: str, body: str, key: str):
        """Envoi mail + Telegram. force=True : jamais de silence sur l'alarme."""
        try:
            notify.send_alert(title, body, key=key, force=True)
            log.info("Envoyé : %s", title)
        except Exception as e:
            log.error("Échec envoi '%s' : %s", title, e)

    # ─── MQTT ────────────────────────────────────────────────────────────────
    def _on_connect(self, c, u, f, rc, props=None):
        log.info("MQTT connecté (rc=%s)", rc)
        for t in ("aegis/alarm/state", "aegis/alarm/event", "aegis/plug/+/state",
                  "aegis/camera/+/state", "aegis/sensor/sirene/state",
                  f"{Z2M}/+", f"{Z2M}/bridge/state"):
            c.subscribe(t)

    def _on_message(self, c, u, msg):
        try:
            payload = msg.payload.decode("utf-8", "replace")
        except Exception:
            return
        topic = msg.topic
        try:
            if topic == "aegis/alarm/state":
                self._alarm_state(json.loads(payload))
            elif topic == "aegis/alarm/event":
                self._alarm_event(json.loads(payload))
            elif topic == f"{Z2M}/bridge/state":
                try:
                    self.bridge_online = json.loads(payload).get("state") == "online"
                except Exception:
                    self.bridge_online = payload.strip() == "online"
            elif topic.startswith("aegis/plug/"):
                d = json.loads(payload)
                with self.lock:
                    self.plugs[topic.split("/")[2]] = d
            elif topic == "aegis/sensor/sirene/state":
                with self.lock:
                    self.sirene = json.loads(payload)
            elif topic.startswith(f"{Z2M}/"):
                name = topic[len(Z2M) + 1:]
                if "/" in name or name.startswith("bridge"):
                    return
                d = json.loads(payload)
                if not isinstance(d, dict):
                    return
                with self.lock:
                    prev = self.z2m.get(name)
                    self.z2m[name] = d
                    self.seen[name] = time.time()
                    if "contact" in d and (not prev or prev.get("contact") != d["contact"]):
                        self.contact_change[name] = time.time()
        except Exception as e:
            log.error("message %s : %s", topic, str(e)[:100])

    # ─── événements alarme ───────────────────────────────────────────────────
    def _alarm_state(self, d: dict):
        with self.lock:
            was_alarm = self.alarm.get("mode") == "alarm"
            self.alarm = d
            now_alarm = d.get("mode") == "alarm"
            if now_alarm and not was_alarm:
                self.alarm_since = time.time()
                self.alarm_repeats = 0
                self.alarm_cams = []
            elif was_alarm and not now_alarm:
                self.alarm_since = 0.0
                self.alarm_trigger = ""
                self.alarm_cams = []

    def _alarm_event(self, ev: dict):
        etype = ev.get("type", "info")
        label = ev.get("label", "")
        detail = ev.get("detail", "")
        heure = _hhmm(ev.get("ts") or time.time())

        if etype == "armed":
            self.send("🛡️ Alarme ARMÉE", f"{detail or label}\nActivée à {heure}.", "armed")
        elif etype == "disarmed":
            self.send("🔓 Alarme DÉSARMÉE", f"{detail or label}\nDésactivée à {heure}.", "disarmed")
        elif etype == "door":
            with self.lock:
                self.alarm_trigger = detail or label
            self.send(f"🚪 Ouverture — {label}",
                      f"{detail}\nDétecté à {heure}.\n"
                      f"Sans désarmement, l'alarme se déclenche.", "door")
        elif etype == "intrusion":
            with self.lock:
                self.alarm_trigger = f"{label} — {detail}" if detail else label
                trig = self.alarm_trigger
                debut = self.alarm_since or (time.time() - 60)
            cams = ", ".join(_cams_detecting(debut)) or "capture en cours…"
            self.send("🚨 INTRUSION",
                      f"Déclencheur : {trig}\nHeure : {heure}\nCaméras : {cams}\n\n"
                      f"Rappel toutes les {REPEAT_S // 60} min jusqu'au désarmement.",
                      "intrusion")
        elif etype == "system":
            self.send(f"ℹ️ {label}", f"{detail}\nÀ {heure}.", "system")

    # ─── rappels pendant une intrusion ───────────────────────────────────────
    def _repeat_loop(self):
        while True:
            time.sleep(5)
            with self.lock:
                active = self.alarm.get("mode") == "alarm" and self.alarm_since > 0
                since = self.alarm_since
                n = self.alarm_repeats
            if not active:
                continue
            if time.time() - since < REPEAT_S * (n + 1):
                continue
            with self.lock:
                self.alarm_repeats += 1
                n = self.alarm_repeats
                trig = self.alarm_trigger or "—"
                depuis = _since(since)
            cams = ", ".join(_cams_detecting(since)) or "aucune image enregistrée"
            self.send(f"🚨 INTRUSION EN COURS — rappel n°{n}",
                      f"Toujours active depuis {depuis}.\n"
                      f"Déclencheur : {trig}\nCaméras ayant détecté : {cams}\n\n"
                      f"L'alarme sonne jusqu'au désarmement depuis l'application.",
                      f"intrusion-repeat-{n}")

    # ─── surveillance du matériel ────────────────────────────────────────────
    def _camera_ok(self, key: str) -> bool:
        try:
            req = urllib.request.Request(f"{GO2RTC_API}/api/frame.jpeg?src={key}")
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.status == 200 and len(r.read()) > 2000
        except Exception:
            return False

    def _scan(self) -> dict:
        """Retourne {clé_anomalie: texte} pour tout ce qui ne va pas."""
        bad: dict[str, str] = {}
        now = time.time()
        armed = self.alarm.get("state") == "armed"
        # Les capteurs Aqara ne parlent que toutes les ~1 h : avant ce délai on
        # ne peut pas conclure qu'un silence est anormal.
        jeune = (now - self.started) < (SENSOR_MUTE_H * 3600)

        if not self.bridge_online:
            bad["bridge"] = "Coordinateur Zigbee hors-ligne (plus aucun capteur supervisé)"

        with self.lock:
            z2m = dict(self.z2m)
            seen = dict(self.seen)
            changes = dict(self.contact_change)
            plugs = dict(self.plugs)
            sirene = dict(self.sirene)

        for g in _registry():
            for d in g.get("devices", []):
                key, label = d["key"], d.get("label", d["key"])
                src, kind = d.get("source"), d.get("kind")

                if src == "zigbee":
                    last = seen.get(key)
                    limit = NODE_TIMEOUT_S if kind == "router" else SENSOR_MUTE_H * 3600
                    if last is None:
                        if not jeune:
                            bad[f"z:{key}"] = f"{label} : aucune remontée"
                    elif now - last > limit:
                        bad[f"z:{key}"] = f"{label} : muet depuis {_since(last)}"
                    bat = (z2m.get(key) or {}).get("battery")
                    if isinstance(bat, (int, float)) and bat < 20:
                        bad[f"bat:{key}"] = f"{label} : batterie à {bat}%"

                elif src == "plug":
                    st = plugs.get(key)
                    if not st:
                        bad[f"p:{key}"] = f"{label} : aucun état reçu"
                    elif not st.get("reachable", True):
                        bad[f"p:{key}"] = f"{label} : injoignable"

                elif src == "camera" and d.get("real"):
                    # Désarmé, les caméras sont hors tension (prises coupées) :
                    # leur silence est normal, on ne le signale pas.
                    if armed and not self._camera_ok(key):
                        bad[f"c:{key}"] = f"Caméra {label} : pas d'image"

                elif src == "siren":
                    if sirene and not sirene.get("reachable", True):
                        bad["siren"] = "Sirène injoignable"
                    b = sirene.get("battery") if sirene else None
                    if isinstance(b, (int, float)) and b < 25:
                        bad["siren-bat"] = f"Sirène : batterie à {b}%"
        return bad

    def _health_loop(self):
        time.sleep(45)          # laisser arriver les états retenus
        while True:
            try:
                bad = self._scan()
                now = time.time()
                nouvelles = []
                for k, txt in bad.items():
                    if k not in self.faults:
                        self.faults[k] = {"since": now, "text": txt}
                        nouvelles.append(txt)
                resolues = [self.faults[k]["text"] for k in list(self.faults) if k not in bad]
                for k in list(self.faults):
                    if k not in bad:
                        del self.faults[k]
                if nouvelles or resolues:
                    self._save()
                if nouvelles:
                    corps = "\n".join(f"• {t}" for t in nouvelles)
                    self.send(f"⚠️ Panne détectée à {_hhmm(now)}",
                              f"{corps}\n\nRappelé dans le récapitulatif quotidien "
                              f"tant que ce n'est pas résolu.", "fault")
                if resolues:
                    corps = "\n".join(f"• {t}" for t in resolues)
                    self.send(f"✅ Rétabli à {_hhmm(now)}", corps, "fault-ok")
            except Exception as e:
                log.error("health : %s", str(e)[:150])
            time.sleep(HEALTH_EVERY_S)

    # ─── récapitulatif quotidien ─────────────────────────────────────────────
    def build_daily(self) -> str:
        """Récapitulatif quotidien : chaque équipement est testé et listé.

        Volontairement exhaustif côté capteurs (état + batterie + dernière
        remontée) : c'est le contrôle matinal qui permet de constater qu'ils
        répondent tous, même quand la maison est vide et qu'aucun ne bouge.
        """
        with self.lock:
            alarm = dict(self.alarm)
            z2m = dict(self.z2m)
            seen = dict(self.seen)
            plugs = dict(self.plugs)
            sirene = dict(self.sirene)
        etat = FR.get(alarm.get("state"), "inconnue")
        depuis = f" depuis {_hhmm(alarm['since'])}" if alarm.get("since") else ""
        L = [f"Alarme : {etat}{depuis}", ""]

        # ── Capteurs d'ouverture : un par ligne, avec batterie ──
        caps = [d for g in _registry() for d in g["devices"]
                if d.get("source") == "zigbee" and d.get("kind") == "contact"]
        vivants = [d for d in caps if seen.get(d["key"])]
        L.append(f"CAPTEURS — {len(vivants)}/{len(caps)} en marche")
        for d in caps:
            key, label = d["key"], d.get("label", d["key"])
            st = z2m.get(key) or {}
            last = seen.get(key)
            if last is None:
                L.append(f"  ❌ {label} : NE RÉPOND PAS")
                continue
            bat = st.get("battery")
            bat_txt = f"{bat}%" if isinstance(bat, (int, float)) else "?"
            ouvert = st.get("contact") is False
            icone = "🟠" if ouvert else "✅"
            L.append(f"  {icone} {label} : en marche — "
                     f"{'OUVERT' if ouvert else 'fermé'} — batterie {bat_txt}")

        # ── Caméras ──
        cams = [d for g in _registry() for d in g["devices"]
                if d.get("source") == "camera" and d.get("real")]
        L.append("")
        if alarm.get("state") == "armed":
            live = [d for d in cams if self._camera_ok(d["key"])]
            L.append(f"CAMÉRAS — {len(live)}/{len(cams)} avec image")
            for d in cams:
                ok = d in live
                L.append(f"  {'✅' if ok else '❌'} {d.get('label', d['key'])} : "
                         f"{'image OK' if ok else 'PAS D IMAGE'}")
        else:
            L.append(f"CAMÉRAS — hors tension ({len(cams)}) : normal, alarme désarmée")

        # ── Prises / sirène / réseau ──
        L.append("")
        pon = [k for k, v in plugs.items() if v.get("reachable")]
        L.append(f"PRISES — {len(pon)}/{len(plugs) or len(pon)} joignables")
        for k, v in sorted(plugs.items()):
            L.append(f"  {'✅' if v.get('reachable') else '❌'} {v.get('label', k)} : "
                     f"{'ON' if v.get('on') else 'off'}")
        if sirene:
            b = sirene.get("battery")
            L.append("")
            L.append(f"SIRÈNE — {'✅ joignable' if sirene.get('reachable') else '❌ INJOIGNABLE'}"
                     f" — batterie {b if b is not None else '?'}%")
        L.append(f"RÉSEAU ZIGBEE — {'✅ en ligne' if self.bridge_online else '❌ HORS LIGNE'}")

        # ── Anomalies persistantes ──
        L.append("")
        if self.faults:
            L.append(f"⚠️ ANOMALIES EN COURS ({len(self.faults)}) :")
            for f in sorted(self.faults.values(), key=lambda x: x["since"]):
                L.append(f"  • {f['text']}")
                L.append(f"    depuis {_hhmm(f['since'])} ({_since(f['since'])})")
        else:
            L.append("✅ Aucune anomalie — tout fonctionne.")
        return "\n".join(L)

    def _daily_loop(self):
        try:
            hh, mm = (int(x) for x in DAILY_AT.split(":"))
        except Exception:
            hh, mm = 8, 0
        while True:
            now = datetime.now()
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            time.sleep(max(30, (target - now).total_seconds()))
            try:
                jour = datetime.now().strftime("%d/%m/%Y")
                self.send(f"📋 Récapitulatif AEGIS — {jour}", self.build_daily(), "daily")
                self.last_daily = jour
                self._save()
            except Exception as e:
                log.error("récap quotidien : %s", str(e)[:150])

    # ─── run ─────────────────────────────────────────────────────────────────
    def run(self):
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.client.loop_start()
        for fn in (self._repeat_loop, self._health_loop, self._daily_loop):
            threading.Thread(target=fn, daemon=True).start()
        log.info("Notifier AEGIS démarré — rappel %ds, récap %s", REPEAT_S, DAILY_AT)
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    Notifier().run()
