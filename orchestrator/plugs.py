"""
plugs.py — Service prises Tapo (P100/P110) : télémétrie + contrôle via python-kasa.

MQTT :
  - publie   aegis/plug/<key>/state  (retained)  {on, reachable, model, rssi, power, energy_*}
  - écoute   aegis/plug/<key>/set    {on: true|false}

Identifiants = compte cloud Tapo (login appli). Vault : TAPO_CLOUD_EMAIL/PASSWORD
(fallback TAPO_USER/PASSWORD). Registre des prises : webapp/devices.yaml (source: plug).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

import paho.mqtt.client as mqtt
import yaml
from dotenv import load_dotenv
from kasa import Credentials, Discover

for vault in ("/home/j.tremont/.secrets/vault.env",
              os.path.join(os.path.dirname(__file__), ".env")):
    if os.path.exists(vault):
        load_dotenv(vault)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("aegis.plugs")

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
POLL_INTERVAL = int(os.getenv("PLUG_POLL_S", "20"))
EMAIL = os.getenv("TAPO_CLOUD_EMAIL") or os.getenv("TAPO_USER")
PASSWORD = os.getenv("TAPO_CLOUD_PASSWORD") or os.getenv("TAPO_PASSWORD")


def _load_plugs() -> dict[str, dict]:
    path = os.path.join(os.path.dirname(__file__), "..", "webapp", "devices.yaml")
    plugs = {}
    for g in yaml.safe_load(open(path))["groups"]:
        for d in g.get("devices", []):
            if d.get("source") == "plug" and d.get("host"):
                plugs[d["key"]] = {"host": d["host"], "label": d.get("label", d["key"])}
    return plugs


class PlugService:
    def __init__(self):
        self.plugs = _load_plugs()
        self.creds = Credentials(EMAIL or "", PASSWORD or "")
        self._devs: dict[str, object] = {}          # key -> kasa Device (cache)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.cmd_q: asyncio.Queue | None = None
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                  client_id="aegis-plugs")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # ─── MQTT (thread paho) ─────────────────────────────────────────────────
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        log.info("MQTT connecté (rc=%s)", reason_code)
        for key in self.plugs:
            client.subscribe(f"aegis/plug/{key}/set")

    def _on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) != 4 or parts[3] != "set":
            return
        key = parts[2]
        try:
            on = bool(json.loads(msg.payload.decode()).get("on"))
        except Exception:
            return
        if self.loop and self.cmd_q is not None:
            self.loop.call_soon_threadsafe(self.cmd_q.put_nowait, (key, on))

    def publish(self, key, payload):
        self.client.publish(f"aegis/plug/{key}/state", json.dumps(payload), retain=True)

    # ─── kasa (boucle async) ────────────────────────────────────────────────
    async def _device(self, key):
        dev = self._devs.get(key)
        if dev is None:
            dev = await Discover.discover_single(self.plugs[key]["host"], credentials=self.creds)
            self._devs[key] = dev
        return dev

    async def _poll(self, key):
        info = self.plugs[key]
        payload = {"key": key, "label": info["label"], "reachable": False, "on": None}
        try:
            dev = await self._device(key)
            await dev.update()
            payload.update(reachable=True, on=bool(dev.is_on),
                           model=dev.model, rssi=dev.rssi)
            em = dev.modules.get("Energy")
            if em is not None:
                payload.update(power=getattr(em, "current_consumption", None),
                               energy_today=getattr(em, "consumption_today", None),
                               energy_month=getattr(em, "consumption_this_month", None),
                               voltage=getattr(em, "voltage", None))
        except Exception as e:
            self._devs.pop(key, None)   # forcer reconnexion au prochain cycle
            log.warning("prise %s injoignable : %s", key, str(e)[:80])
        self.publish(key, payload)

    async def _apply(self, key, on):
        try:
            dev = await self._device(key)
            await (dev.turn_on() if on else dev.turn_off())
            log.info("prise %s -> %s", key, "ON" if on else "OFF")
        except Exception as e:
            self._devs.pop(key, None)
            log.error("commande prise %s échouée : %s", key, str(e)[:80])
        await self._poll(key)

    async def main(self):
        self.loop = asyncio.get_running_loop()
        self.cmd_q = asyncio.Queue()
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.client.loop_start()
        if not EMAIL or not PASSWORD:
            log.warning("Identifiants cloud Tapo absents (TAPO_CLOUD_EMAIL/PASSWORD).")
        log.info("Service prises démarré (%d prises)", len(self.plugs))
        await asyncio.gather(*(self._poll(k) for k in self.plugs))
        while True:
            try:
                key, on = await asyncio.wait_for(self.cmd_q.get(), timeout=POLL_INTERVAL)
                await self._apply(key, on)
            except asyncio.TimeoutError:
                await asyncio.gather(*(self._poll(k) for k in self.plugs))


if __name__ == "__main__":
    asyncio.run(PlugService().main())
