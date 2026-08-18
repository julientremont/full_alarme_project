"""
camera.py — Pilotage caméra Tapo (C210) : privacy, sirène, mouvement, YOLO.
- Désarmé  -> privacy ON  (objectif coupé, ne filme pas).
- Armé     -> privacy OFF (flux dispo) ; veille mouvement (2 s) puis YOLO.
- Alarme   -> startManualAlarm (sirène) sur la caméra ; captures + YOLO périodiques.
Modèle YOLO chargé une fois, inférence sérialisée (Pi).
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
import urllib.request
from datetime import datetime

import cv2
import numpy as np
from pytapo import Tapo
from ultralytics import YOLO

import storage

# Cap le temps d'ouverture RTSP (évite qu'une caméra injoignable bloque la veille)
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS",
                      "rtsp_transport;tcp|stimeout;5000000")

# API go2rtc : snapshots JPEG rapides (go2rtc maintient la connexion caméra ->
# pas de handshake RTSP par cycle). Fallback = RTSP direct.
GO2RTC_API = os.getenv("GO2RTC_API", "http://127.0.0.1:1984")

log = logging.getLogger("aegis.orch.camera")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "yolov8n.pt")
OBJECTS = {0: "Personne", 43: "Couteau", 76: "Ciseaux", 34: "Batte"}  # 34=baseball bat (39=bottle, corrigé)

_model: YOLO | None = None
_model_lock = threading.Lock()


def _get_model() -> YOLO:
    global _model
    if _model is None:
        log.info("Chargement du modèle YOLO…")
        _model = YOLO(MODEL_PATH)
        log.info("YOLO prêt")
    return _model


class Camera:
    def __init__(self, *, key, label, room, host, ctrl_user, ctrl_password,
                 rtsp_user, rtsp_password, stream, onboard_siren=True):
        self.key = key
        self.label = label
        self.room = room
        self.host = host
        # Contrôle pytapo = auth LOCALE directe (user "admin" + mot de passe du
        # compte cloud). Pas de round-trip vers les serveurs TP-Link -> pas de
        # « Temporary Suspension » (les handshakes cloud répétés déclenchaient le verrou).
        self.ctrl_user = ctrl_user
        self.ctrl_password = ctrl_password
        self.onboard_siren = onboard_siren    # alarme embarquée (sirène caméra sur SA détection)
        self.entry_zone = False               # zone temporisée (délai sortie/entrée) — fixé par l'orchestrateur
        self.rtsp_user = rtsp_user
        self.rtsp_password = rtsp_password
        self.stream = stream
        self._ctrl_lock = threading.Lock()   # sérialise les accès pytapo (1 session)
        self._tapo: Tapo | None = None        # session pytapo réutilisée (limite les handshakes)
        self._privacy: bool | None = None     # dernier état privacy connu (évite les toggles inutiles)
        self._suspended_until: float = 0.0    # ne plus solliciter la caméra tant que < now (anti-relance du verrou)
        # Réglages détection (pilotables depuis l'app via aegis/detection/config).
        self.classes = set(OBJECTS)           # classes YOLO surveillées
        self.conf = float(os.getenv("YOLO_CONF", "0.45"))   # seuil de confiance (0.8 ratait les passages)
        self.motion_seuil = int(os.getenv("MOTION_SEUIL", "60000"))  # seuil de différence d'images (veille)

    def apply_detection_config(self, *, classes=None, conf=None, motion_seuil=None) -> None:
        if classes is not None:
            self.classes = {c for c in classes if c in OBJECTS}
        if conf is not None:
            self.conf = float(conf)
        if motion_seuil is not None:
            self.motion_seuil = int(motion_seuil)

    # ─── contrôle pytapo (privacy + sirène) ──────────────────────────────────
    def _do(self, fn_name, *args, quiet: bool = False) -> bool:
        """Réutilise la session pytapo ; ne la recrée qu'en cas d'échec (+1 retry).
        Le C210 suspend l'auth si trop de handshakes rapprochés.
        `quiet` : log l'échec en DEBUG au lieu d'ERROR (essais sirène en cascade)."""
        with self._ctrl_lock:
            if time.time() < self._suspended_until:
                return False                   # verrou connu : ne pas relancer le compteur
            last = None
            for attempt in range(2):
                try:
                    if self._tapo is None:
                        # Auth LOCALE (sans cloudPassword) : directe sur la caméra.
                        self._tapo = Tapo(self.host, self.ctrl_user, self.ctrl_password)
                    getattr(self._tapo, fn_name)(*args)
                    return True
                except Exception as e:
                    last = e
                    self._tapo = None          # forcer une reconnexion propre
                    if "Suspension" in str(e):
                        m = re.search(r"in (\d+) seconds", str(e))
                        self._suspended_until = time.time() + (int(m.group(1)) if m else 1800)
                        break                  # ne pas insister (ça relance le verrou)
                    time.sleep(0.5)
            log.log(logging.DEBUG if quiet else logging.ERROR,
                    "%s() caméra %s : %s", fn_name, self.label, last)
            return False

    def set_privacy(self, enabled: bool) -> bool:
        if self._privacy == enabled:
            return True                       # déjà dans l'état voulu → aucun handshake
        ok = self._do("setPrivacyMode", enabled)
        if ok:
            self._privacy = enabled
            log.info("Caméra %s : privacy %s", self.label, "ON (coupée)" if enabled else "OFF (active)")
        return ok

    def start_siren(self) -> bool:
        """Sirène caméra en best-effort : les firmwares diffèrent (C210/C200C
        renvoient souvent -40106/-40210). On tente plusieurs API ; le vrai
        avertisseur reste la sirène matérielle MQTT (cf. alarm.py). Non bloquant
        côté orchestrateur (appelé dans un worker)."""
        for fn, args in (("startManualAlarm", ()),
                         ("setSirenStatus", (True,)),
                         ("playAlarm", (300, 0, "high"))):
            if self._do(fn, *args, quiet=True):
                log.warning("Caméra %s : SIRÈNE ON (%s)", self.label, fn)
                return True
        log.warning("Caméra %s : sirène non supportée (firmware) — sirène MQTT requise", self.label)
        return False

    def stop_siren(self) -> bool:
        """Coupe la sirène par toutes les voies possibles (on ne sait pas
        laquelle l'a démarrée). Best-effort, ne lève jamais."""
        ok = False
        for fn, args in (("stopManualAlarm", ()), ("setSirenStatus", (False,))):
            if self._do(fn, *args, quiet=True):
                ok = True
        if ok:
            log.info("Caméra %s : sirène OFF", self.label)
        return ok

    def set_onboard_alarm(self, on: bool) -> bool:
        """Alarme embarquée : la caméra sonne sa sirène + lumière dès qu'ELLE
        détecte du mouvement (seul mode audible sur firmware sans trigger manuel).
        Volume haut, 300 s. Activée à l'armement, coupée au désarmement."""
        if not self.onboard_siren:
            return False
        ok = self._do("setAlarm", bool(on), True, True, "high", 300)
        if ok:
            log.warning("Caméra %s : alarme embarquée %s", self.label, "ON" if on else "OFF")
        return ok

    # ─── flux ────────────────────────────────────────────────────────────────
    # Acquisition via snapshot HTTP go2rtc (go2rtc maintient LA connexion caméra) :
    # pas de handshake RTSP par cycle -> beaucoup plus réactif. Fallback RTSP direct.
    def _rtsp_url(self) -> str:
        gw = os.getenv("GO2RTC_RTSP", "rtsp://127.0.0.1:8554")
        if gw:
            return f"{gw}/{self.key}"
        return f"rtsp://{self.rtsp_user}:{self.rtsp_password}@{self.host}:554/{self.stream}"

    def _snapshot(self):
        """Frame courante via go2rtc (rapide). Fallback RTSP si indisponible."""
        if GO2RTC_API:
            try:
                url = f"{GO2RTC_API}/api/frame.jpeg?src={self.key}"
                with urllib.request.urlopen(url, timeout=4) as r:
                    buf = r.read()
                img = cv2.imdecode(np.frombuffer(buf, dtype=np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    return img
            except Exception:
                pass
        return self._grab_rtsp()

    def _grab_rtsp(self):
        cap = cv2.VideoCapture(self._rtsp_url())
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        cap.release()
        return frame if ok else None

    def motion(self, gap: float = 1.0, seuil: int | None = None):
        """Mouvement = différence entre 2 snapshots espacés de `gap` s.
        Retourne (bool mouvement, dernière frame) ; la frame sert au YOLO."""
        if seuil is None:
            seuil = self.motion_seuil
        f1 = self._snapshot()
        if f1 is None:
            return False, None
        time.sleep(gap)
        f2 = self._snapshot()
        if f2 is None:
            return False, None
        g1 = cv2.cvtColor(cv2.resize(f1, (640, 360)), cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(cv2.resize(f2, (640, 360)), cv2.COLOR_BGR2GRAY)
        diff = int(np.sum(cv2.absdiff(g1, g2)))
        return diff > seuil, f2

    def grab(self):
        return self._snapshot()

    def detect(self, frame, *, save: bool = True) -> bool:
        """YOLO sur une frame. Sauvegarde une capture par objet détecté.
        Retourne True si une personne/objet surveillé est détecté."""
        if frame is None:
            return False
        frame = cv2.resize(frame, (1280, 720))
        found = False
        with _model_lock:
            results = _get_model()(frame, conf=self.conf, verbose=False)
        for result in results:
            if result.boxes is None or result.boxes.cls is None:
                continue
            for idx, cls in enumerate(result.boxes.cls):
                cls_id = int(cls)
                if cls_id not in self.classes:
                    continue
                found = True
                if save:
                    conf = float(result.boxes.conf[idx])
                    box = result.boxes.xyxy[idx].cpu().numpy()
                    self._save(frame, box, OBJECTS[cls_id], conf)
        return found

    def snapshot_detect(self, *, save: bool = True) -> bool:
        return self.detect(self.grab(), save=save)

    def capture_always(self, run_yolo: bool = True) -> bool:
        """Sauvegarde une image de la caméra (preuve). Retourne True si YOLO trouve.
        ⚠️ Pendant une alarme ACTIVE : run_yolo=False → on NE relance PAS YOLO
        (inutile, l'intrusion est déjà confirmée) pour ne PAS saturer le Pi, ce qui
        affamait le thread MQTT et empêchait le désarmement. On sauve juste la frame."""
        frame = self.grab()
        if frame is None:
            return False
        if run_yolo:
            if self.detect(frame, save=True):    # sauve annoté si objet trouvé
                return True
        # frame brute (pas de détection, ou YOLO volontairement désactivé)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ok, buf = cv2.imencode(".jpg", cv2.resize(frame, (1280, 720)))
        if ok:
            storage.save_capture(buf.tobytes(), f"{self.label}_Vue_{ts}.jpg")
        return False

    def _save(self, frame, box, name, conf):
        x1, y1, x2, y2 = map(int, box)
        annotated = frame.copy()
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(annotated, f"{name}: {conf:.2f}", (x1, max(0, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        ok, buf = cv2.imencode(".jpg", annotated)
        if ok:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            storage.save_capture(buf.tobytes(), f"{self.label}_{name}_{ts}.jpg")
