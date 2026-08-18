"""
tuya_siren.py — Sirène WiFi Tuya 3-en-1 (sirène + température + humidité).
Contrôle LOCAL via tinytuya (protocole 3.5) — pas de cloud, faible latence.

MQTT :
  - publie  aegis/sensor/sirene/state (retained)
            {reachable, temperature, humidity, battery, volume, ringtone, duration, alarm}
  - écoute  aegis/siren/set  {on, volume, ringtone, duration, test}

Le déclenchement d'alarme passe par {"on": true} (publié par l'orchestrateur via
`_ext_siren`), coupé par {"on": false} au désarmement. Tant que « on », la sirène
est ré-affirmée périodiquement (la durée interne du device pourrait la couper).

Identifiants dans le vault : TUYA_SIREN_ID / TUYA_SIREN_IP / TUYA_SIREN_KEY / TUYA_SIREN_VERSION.
Correspondance des « data points » (modèle Tuya) découverte via l'API cloud.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time

import paho.mqtt.client as mqtt
import tinytuya
from dotenv import load_dotenv

for vault in ("/home/j.tremont/.secrets/vault.env",
              os.path.join(os.path.dirname(__file__), ".env")):
    if os.path.exists(vault):
        load_dotenv(vault)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("aegis.siren")

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
POLL_S = int(os.getenv("SIREN_POLL_S", "60"))
DID = os.getenv("TUYA_SIREN_ID")
IP = os.getenv("TUYA_SIREN_IP")
KEY = os.getenv("TUYA_SIREN_KEY")
VER = float(os.getenv("TUYA_SIREN_VERSION", "3.5"))

T_STATE = "aegis/sensor/sirene/state"
T_SET = "aegis/siren/set"

# Data points (modèle Tuya de cette sirène)
DP_BATT = 101      # niveau batterie 0-4
DP_RING = 102      # mélodie/sonnerie 1-12
DP_DUR = 103       # durée (s) 0-1800
DP_ALARM = 104     # sirène on/off (bool)
DP_TEMP = 105      # température ×10 (°C)
DP_HUM = 106       # humidité (%RH)
DP_VOL = 116       # volume 0/1/2 — échelle inversée sur ce modèle : 0 = fort, 2 = bas

VOL_HIGH, VOL_MID, VOL_LOW = "0", "1", "2"
# Volume imposé quand l'alarme sonne — jamais le réglage confort de l'utilisateur.
ALARM_VOL = os.getenv("SIREN_ALARM_VOLUME", VOL_HIGH)


class SirenService:
    def __init__(self):
        self.lock = threading.Lock()
        self._dev: tinytuya.Device | None = None
        self._siren_on = False
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                  client_id="aegis-siren")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # ─── accès tinytuya (sérialisé) ──────────────────────────────────────────
    def _device(self) -> tinytuya.Device:
        if self._dev is None:
            self._dev = tinytuya.Device(DID, IP, KEY, version=VER)
            self._dev.set_socketTimeout(6)
        return self._dev

    def _read_dps(self):
        with self.lock:
            try:
                s = self._device().status()
                if isinstance(s, dict) and "dps" in s:
                    return s["dps"]
            except Exception as e:
                log.warning("lecture sirène : %s", str(e)[:80])
            self._dev = None
            return None

    def _set(self, dp: int, val) -> bool:
        with self.lock:
            try:
                self._device().set_value(dp, val)
                return True
            except Exception as e:
                log.error("commande sirène dp%s=%s : %s", dp, val, str(e)[:80])
                self._dev = None
                return False

    # ─── MQTT ────────────────────────────────────────────────────────────────
    def _on_connect(self, c, u, f, rc, props=None):
        log.info("MQTT connecté (rc=%s)", rc)
        c.subscribe(T_SET)

    def _on_message(self, c, u, msg):
        try:
            d = json.loads(msg.payload.decode())
        except Exception:
            return
        if not isinstance(d, dict):
            return
        if "volume" in d:
            self._set(DP_VOL, str(int(d["volume"])))          # 0/1/2
        if "ringtone" in d:
            self._set(DP_RING, str(int(d["ringtone"])))        # 1-12
        if "duration" in d:
            self._set(DP_DUR, max(0, min(1800, int(d["duration"]))))
        if d.get("test"):
            self._set(DP_ALARM, True)
            time.sleep(2)
            if not self._siren_on:
                self._set(DP_ALARM, False)
        if "on" in d:
            on = bool(d["on"])
            with self.lock:
                self._siren_on = on
            if on:
                self._set(DP_VOL, ALARM_VOL)                   # alarme = volume MAX (0)
            self._set(DP_ALARM, on)
            log.warning("SIRÈNE %s", "ON" if on else "OFF")
        self.publish()

    def publish(self):
        dps = self._read_dps()
        payload: dict = {"reachable": dps is not None, "ts": time.time()}
        if dps:
            try:
                payload["temperature"] = round(int(dps.get(str(DP_TEMP), dps.get(DP_TEMP, 0))) / 10, 1)
            except (TypeError, ValueError):
                pass
            hum = dps.get(str(DP_HUM), dps.get(DP_HUM))
            payload["humidity"] = int(hum) if hum is not None else None
            batt = dps.get(str(DP_BATT), dps.get(DP_BATT))
            try:
                payload["battery"] = int(batt) * 25 if batt is not None else None   # 0-4 -> 0-100 %
            except (TypeError, ValueError):
                pass
            payload["volume"] = dps.get(str(DP_VOL), dps.get(DP_VOL))
            payload["ringtone"] = dps.get(str(DP_RING), dps.get(DP_RING))
            payload["duration"] = dps.get(str(DP_DUR), dps.get(DP_DUR))
            payload["alarm"] = bool(dps.get(str(DP_ALARM), dps.get(DP_ALARM)))
        self.client.publish(T_STATE, json.dumps(payload), retain=True)

    # ─── ré-affirmation de la sirène (survit à la durée interne du device) ────
    def _reassert_loop(self):
        while True:
            time.sleep(20)
            with self.lock:
                on = self._siren_on
            if on:
                self._set(DP_VOL, ALARM_VOL)                   # garde le volume max
                self._set(DP_ALARM, True)

    def run(self):
        if not (DID and IP and KEY):
            log.error("Identifiants sirène absents (TUYA_SIREN_ID/IP/KEY)")
            return
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.client.loop_start()
        threading.Thread(target=self._reassert_loop, daemon=True).start()
        log.info("Service sirène démarré (%s @ %s, v%s)", DID, IP, VER)
        while True:
            self.publish()
            time.sleep(POLL_S)


if __name__ == "__main__":
    SirenService().run()
