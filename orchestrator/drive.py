"""
drive.py — Sauvegarde hors-site des captures sur Google Drive (OAuth).

Rangement : <dossier base>/<Caméra>/<AAAA-MM-JJ>/<fichier>.jpg
But (cf. docs/13 P0 #1) : les preuves survivent au vol/destruction du Pi.

Auth OAuth (comme l'ancien projet Security) : upload sous le compte Google de
l'utilisateur. Le compte de service est impossible ici (« Service Accounts do not
have storage quota » sur un Drive perso). Token régénéré une seule fois via
`setup_gdrive_auth.py`, puis rafraîchi automatiquement.

Config (vault) : GOOGLE_CREDENTIALS_PATH (client OAuth « installed »),
PATH_DRIVE_ENTREE_TAPO_CAPTURES (dossier base), GDRIVE_TOKEN_PATH (token, défaut
/home/j.tremont/.secrets/gdrive_token.json), DRIVE_UPLOAD=0 pour désactiver.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from io import BytesIO

log = logging.getLogger("aegis.orch.drive")

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

_lock = threading.Lock()
_service = None
_folder_cache: dict[tuple, str] = {}


# ─── config (lue paresseusement : le vault est chargé après l'import) ──────────
def _client_secret() -> str:
    return os.getenv("GOOGLE_CREDENTIALS_PATH", "")


def _token_path() -> str:
    return os.getenv("GDRIVE_TOKEN_PATH", "/home/j.tremont/.secrets/gdrive_token.json")


def _base_folder() -> str:
    return os.getenv("PATH_DRIVE_ENTREE_TAPO_CAPTURES", "")


def _enabled() -> bool:
    return os.getenv("DRIVE_UPLOAD", "1").lower() not in ("0", "false", "no", "")


def available() -> bool:
    return _enabled() and bool(_base_folder() and os.path.exists(_token_path()))


# ─── service Drive (token OAuth, auto-refresh) ────────────────────────────────
def _load_service():
    global _service
    if _service is not None:
        return _service
    if not (_base_folder() and os.path.exists(_token_path())):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_info(json.load(open(_token_path())), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(_token_path(), "w") as f:
                f.write(creds.to_json())
        if not creds.valid:
            log.error("Token Drive invalide — relancer setup_gdrive_auth.py")
            return None
        _service = build("drive", "v3", credentials=creds, cache_discovery=False)
        log.info("Google Drive OK (upload hors-site actif)")
        return _service
    except Exception as e:
        log.error("Init Drive échouée : %s", str(e)[:120])
        return None


def _folder(service, name: str, parent: str) -> str:
    """Trouve (ou crée) un sous-dossier `name` sous `parent`. Résultat mis en cache."""
    key = (parent, name)
    if key in _folder_cache:
        return _folder_cache[key]
    safe = name.replace("'", " ")
    q = (f"name = '{safe}' and '{parent}' in parents and "
         "mimeType = 'application/vnd.google-apps.folder' and trashed = false")
    items = service.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
    if items:
        fid = items[0]["id"]
    else:
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]}
        fid = service.files().create(body=meta, fields="id").execute()["id"]
    _folder_cache[key] = fid
    return fid


def upload(image_bytes: bytes, filename: str, camera: str, day: str) -> str | None:
    """Upload une capture dans <base>/<camera>/<day>/. Best-effort, ne lève jamais
    (appelé en tâche de fond). Retourne l'id Drive ou None."""
    if not _enabled():
        return None
    with _lock:                                   # sérialise (1 session Drive)
        service = _load_service()
        if service is None:
            return None
        try:
            from googleapiclient.http import MediaIoBaseUpload
            cam_folder = _folder(service, camera or "Autre", _base_folder())
            day_folder = _folder(service, day, cam_folder)
            media = MediaIoBaseUpload(BytesIO(image_bytes), mimetype="image/jpeg", resumable=False)
            fid = service.files().create(
                body={"name": filename, "parents": [day_folder]},
                media_body=media, fields="id").execute()["id"]
            log.info("Drive ↑ %s/%s/%s", camera, day, filename)
            return fid
        except Exception as e:
            global _service
            _service = None                        # forcer une reconnexion au prochain envoi
            log.warning("Upload Drive échoué (%s) : %s", filename, str(e)[:100])
            return None
