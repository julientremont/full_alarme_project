"""
mqtt_state.py — Client MQTT en arrière-plan : s'abonne à Zigbee2MQTT,
maintient un registre d'état en mémoire et journalise les événements capteurs.
"""
from __future__ import annotations

import json
import logging
import threading
import time

import paho.mqtt.client as mqtt

import database as db

log = logging.getLogger("aegis.mqtt")

# Délais (s) au-delà desquels un device est considéré hors-ligne
ROUTER_TIMEOUT = 120        # routeurs/prises : rapportent ~10s
SENSOR_TIMEOUT = 3 * 3600   # capteurs Aqara : keep-alive ~1h, marge x3


class MqttState:
    def __init__(self, base_topic: str = "zigbee2mqtt"):
        self.base = base_topic
        self._lock = threading.Lock()
        self._states: dict[str, dict] = {}   # friendly_name -> last payload (dict)
        self._seen: dict[str, float] = {}     # friendly_name -> last_seen epoch
        self.bridge_online = False
        self.connected = False
        self.alarm = {"state": "unknown", "mode": "idle", "since": None}
        self.camera_live: dict[str, dict] = {}   # label -> {reachable, privacy, ts}
        self.plug_states: dict[str, dict] = {}   # key -> {on, reachable, power, ...}
        self.siren_state: dict = {}              # {temperature, humidity, battery, volume, ringtone, alarm, reachable}
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="aegis-webapp",
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    # ─── lifecycle ───────────────────────────────────────────────────────────
    def start(self, host: str, port: int = 1883, username=None, password=None):
        if username:
            self.client.username_pw_set(username, password)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        try:
            self.client.connect_async(host, port, keepalive=60)
        except Exception as e:  # pragma: no cover
            log.error("connexion MQTT échouée: %s", e)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic: str, payload: dict, retain: bool = False):
        """Publie un message JSON sur le bus (commandes alarme)."""
        self.client.publish(topic, json.dumps(payload), retain=retain)

    def alarm_state(self) -> dict:
        with self._lock:
            return dict(self.alarm)

    # ─── callbacks ───────────────────────────────────────────────────────────
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = (getattr(reason_code, "value", reason_code) == 0)
        log.info("MQTT connecté (rc=%s)", reason_code)
        client.subscribe(f"{self.base}/bridge/state")
        client.subscribe(f"{self.base}/+")          # états devices (friendly_name)
        client.subscribe("aegis/alarm/state")       # état alarme (orchestrateur)
        client.subscribe("aegis/alarm/event")       # événements alarme à journaliser
        client.subscribe("aegis/camera/+/state")    # état caméras (orchestrateur, 1 topic/caméra)
        client.subscribe("aegis/plug/+/state")      # état prises Tapo
        client.subscribe("aegis/sensor/sirene/state")  # sirène Tuya (temp/humidité/volume…)

    def _on_disconnect(self, *args, **kwargs):
        self.connected = False
        log.warning("MQTT déconnecté")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = msg.payload.decode("utf-8", "replace")
        except Exception:
            return

        if topic == f"{self.base}/bridge/state":
            try:
                self.bridge_online = json.loads(payload).get("state") == "online"
            except Exception:
                self.bridge_online = (payload.strip() == "online")
            return

        if topic == "aegis/alarm/state":
            try:
                with self._lock:
                    self.alarm = json.loads(payload)
            except Exception:
                pass
            return

        if topic == "aegis/alarm/event":
            try:
                ev = json.loads(payload)
                db.log_event("alarm", ev.get("type", "info"),
                             device=ev.get("label"), detail=ev.get("detail"))
            except Exception:
                pass
            return

        if topic.startswith("aegis/camera/") and topic.endswith("/state"):
            try:
                cs = json.loads(payload)
                with self._lock:
                    self.camera_live[cs.get("label", "")] = cs
            except Exception:
                pass
            return

        if topic.startswith("aegis/plug/") and topic.endswith("/state"):
            try:
                ps = json.loads(payload)
                with self._lock:
                    self.plug_states[topic.split("/")[2]] = ps
            except Exception:
                pass
            return

        if topic == "aegis/sensor/sirene/state":
            try:
                with self._lock:
                    self.siren_state = json.loads(payload)
            except Exception:
                pass
            return

        # zigbee2mqtt/<friendly_name>
        prefix = f"{self.base}/"
        if not topic.startswith(prefix):
            return
        name = topic[len(prefix):]
        if "/" in name or name.startswith("bridge"):
            return  # sous-topics (set/get/availability/bridge…) ignorés ici
        try:
            data = json.loads(payload)
        except Exception:
            return
        if not isinstance(data, dict):
            return

        with self._lock:
            prev = self._states.get(name)
            self._states[name] = data
            self._seen[name] = time.time()

        # Journaliser les changements de contact (capteurs d'ouverture)
        if "contact" in data:
            new_c = data["contact"]
            old_c = prev.get("contact") if prev else None
            if old_c is None or old_c != new_c:
                # contact True = fermé, False = ouvert
                db.log_event("sensor", "close" if new_c else "open", device=name)

    # ─── lecture ─────────────────────────────────────────────────────────────
    def raw(self, name: str) -> dict | None:
        with self._lock:
            d = self._states.get(name)
            return dict(d) if d else None

    def last_seen(self, name: str) -> float | None:
        with self._lock:
            return self._seen.get(name)

    def device_status(self, dev: dict) -> dict:
        """Calcule le statut d'un device du registre (devices.yaml)."""
        src = dev.get("source")
        key = dev["key"]
        now = time.time()
        out = {"key": key, "label": dev.get("label", key), "room": dev.get("room", ""),
               "icon": dev.get("icon", "dot"), "source": src,
               "status": "unknown", "color": "gray", "text": "—", "extra": {}}

        if src == "bridge":
            online = self.bridge_online and self.connected
            out.update(status="online" if online else "offline",
                       color="green" if online else "red",
                       text="En ligne" if online else "Hors ligne")
            return out

        if src == "zigbee":
            raw = self.raw(key)
            seen = self.last_seen(key)
            kind = dev.get("kind")
            if raw is None or seen is None:
                # jamais reçu depuis le démarrage (capteur endormi, pas encore de message retenu)
                out.update(status="waiting", color="gray", text="En attente")
                return out
            if kind == "contact":
                if (now - seen) > SENSOR_TIMEOUT:
                    out.update(status="offline", color="red", text="Hors ligne")
                else:
                    closed = raw.get("contact", True)
                    out.update(status="closed" if closed else "open",
                               color="blue" if closed else "orange",
                               text="Fermé" if closed else "Ouvert",
                               extra={"battery": raw.get("battery"), "lqi": raw.get("linkquality")})
                return out
            # routeur / prise
            if (now - seen) > ROUTER_TIMEOUT:
                out.update(status="offline", color="red", text="Hors ligne")
            else:
                out.update(status="online", color="green", text="En ligne",
                           extra={"lqi": raw.get("linkquality"), "power": raw.get("power")})
            return out

        if src == "plug":
            with self._lock:
                ps = self.plug_states.get(key)
            if not ps:
                out.update(status="waiting", color="gray", text="En attente")
            elif not ps.get("reachable"):
                out.update(status="offline", color="red", text="Injoignable")
            else:
                on = bool(ps.get("on"))
                extra = {}
                if ps.get("power") is not None:
                    extra["power"] = ps.get("power")
                if ps.get("energy_today") is not None:
                    extra["energy_today"] = ps.get("energy_today")
                if ps.get("rssi") is not None:
                    extra["rssi"] = ps.get("rssi")
                out.update(status="on" if on else "off",
                           color="green" if on else "gray",
                           text="Allumée" if on else "Éteinte",
                           controllable=True, on=on, extra=extra)
            return out

        if src == "camera" and dev.get("real"):
            with self._lock:
                cs = self.camera_live.get(dev.get("label", ""))
            if not cs:
                out.update(status="waiting", color="gray", text="En attente")
            elif not cs.get("reachable"):
                out.update(status="offline", color="red", text="Injoignable")
            elif cs.get("privacy"):
                out.update(status="standby", color="blue", text="En veille (privacy)")
            else:
                out.update(status="online", color="green", text="Active")
            return out

        if src == "siren":
            with self._lock:
                ss = dict(self.siren_state)
            if not ss:
                out.update(status="waiting", color="gray", text="En attente")
            elif not ss.get("reachable"):
                out.update(status="offline", color="red", text="Injoignable")
            else:
                t = ss.get("temperature")
                h = ss.get("humidity")
                alarm = ss.get("alarm")
                out.update(
                    status="alarm" if alarm else "online",
                    color="red" if alarm else "green",
                    text="🚨 En alarme" if alarm else (
                        f"{t} °C · {h} %" if t is not None and h is not None else "Prête"),
                    extra={"temperature": t, "humidity": h, "battery": ss.get("battery"),
                           "volume": ss.get("volume"), "ringtone": ss.get("ringtone"),
                           "duration": ss.get("duration")})
            return out

        # doorbell / autres non installés
        out.update(status="unknown", color="gray", text="Non installé")
        return out
