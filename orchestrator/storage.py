"""
storage.py — Stockage local des captures (servi par l'app AEGIS).
Remplace Google Drive : pas de dépendance externe, toujours disponible.
Rétention automatique (garde les N dernières captures).
"""
from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime

try:
    import drive
except Exception:                                  # google libs absentes -> upload désactivé
    drive = None

log = logging.getLogger("aegis.orch.storage")

# Dossier servi par la webapp (onglet Caméras).
CAPTURES_DIR = os.getenv(
    "CAPTURES_DIR",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "webapp", "captures")),
)
MAX_CAPTURES = int(os.getenv("MAX_CAPTURES", "500"))


def _prune():
    try:
        files = [os.path.join(CAPTURES_DIR, f) for f in os.listdir(CAPTURES_DIR)
                 if f.lower().endswith(".jpg")]
        if len(files) <= MAX_CAPTURES:
            return
        files.sort(key=os.path.getmtime)
        for path in files[:len(files) - MAX_CAPTURES]:
            try:
                os.remove(path)
            except OSError:
                pass
    except Exception as e:
        log.warning("purge captures : %s", e)


def _meta(filename: str) -> tuple[str, str]:
    """Extrait (caméra, jour AAAA-MM-JJ) du nom « <Label>_<Objet>_<date>_<heure>.jpg »."""
    camera = filename.split("_", 1)[0] or "Autre"
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    day = m.group(1) if m else datetime.now().strftime("%Y-%m-%d")
    return camera, day


def save_capture(image_bytes: bytes, filename: str) -> str | None:
    """Écrit une capture JPEG dans CAPTURES_DIR (local) et la pousse hors-site sur
    Google Drive en tâche de fond (rangée par caméra/date). Retourne le chemin local."""
    try:
        os.makedirs(CAPTURES_DIR, exist_ok=True)
        path = os.path.join(CAPTURES_DIR, filename)
        with open(path, "wb") as f:
            f.write(image_bytes)
        _prune()
        log.info("Capture enregistrée : %s", filename)
    except Exception as e:
        log.error("Échec écriture capture (%s) : %s", filename, e)
        path = None
    # Sauvegarde hors-site (best-effort, ne bloque jamais l'alarme)
    if drive is not None and drive.available():
        cam, day = _meta(filename)
        threading.Thread(target=drive.upload, args=(image_bytes, filename, cam, day),
                         daemon=True).start()
    return path
