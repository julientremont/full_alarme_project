"""
notify.py — Alertes courtes AEGIS sur 2 canaux : e-mail + Telegram.
Même contenu sur les deux. Anti-spam par clé (cooldown), sauf force=True.
Config (vault) : MAIL_ENVOI/RECEPTION/MP, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS (CSV).
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import time
import urllib.parse
import urllib.request
from email.mime.text import MIMEText

log = logging.getLogger("aegis.orch.notify")

APP_URL = os.getenv("AEGIS_APP_URL", "https://aegis.tremontraimi.com")
COOLDOWN = int(os.getenv("ALERT_COOLDOWN_S", "300"))
_last_sent: dict[str, float] = {}


def _can_send(key: str) -> bool:
    now = time.time()
    if now - _last_sent.get(key, 0) < COOLDOWN:
        return False
    _last_sent[key] = now
    return True


DB_PATH = os.getenv("AEGIS_DB_PATH",
                    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "webapp", "aegis.db")))


def _db_values(kind: str) -> list[str]:
    """Destinataires actifs depuis la base (gérés dans l'admin)."""
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=3)
        rows = con.execute("SELECT value FROM recipients WHERE kind=? AND active=1", (kind,)).fetchall()
        con.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def _mail_recipients() -> list[str]:
    vals = _db_values("email")
    if vals:
        return vals
    return [a.strip() for a in os.getenv("MAIL_RECEPTION", "").split(",") if a.strip()]


def _telegram_chat_ids() -> list[str]:
    vals = _db_values("telegram")
    if vals:
        return vals
    return [c.strip() for c in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]


def _send_email(subject: str, body: str) -> None:
    sender = os.getenv("MAIL_ENVOI")
    app_password = os.getenv("MAIL_MP")
    recipients = _mail_recipients()
    if not (sender and app_password and recipients):
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(sender, app_password)
            server.sendmail(sender, recipients, msg.as_string())
        log.info("Mail envoyé → %s : %s", recipients, subject)
    except Exception as e:
        log.error("Échec mail : %s", e)


def _send_telegram(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids = _telegram_chat_ids()
    if not token or not chat_ids:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chat_id in chat_ids:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text,
                                       "disable_web_page_preview": "true"}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
                if r.status != 200:
                    log.error("Telegram %s : HTTP %s", chat_id, r.status)
        except Exception as e:
            log.error("Échec Telegram %s : %s", chat_id, str(e)[:80])


def send_alert(title: str, line: str, *, key: str, force: bool = False) -> bool:
    """Envoie une alerte (mail + Telegram). `key` regroupe l'anti-spam.
    `force` ignore le cooldown (armement/désarmement, ouverture)."""
    if not force and not _can_send(key):
        log.info("Alerte '%s' ignorée (cooldown)", key)
        return False
    heure = time.strftime("%H:%M")
    subject = f"AEGIS — {title}"
    body = f"{line}\n\nHeure : {heure}\nApp : {APP_URL}"
    _send_email(subject, body)
    _send_telegram(f"🛡️ AEGIS — {title}\n{line}\n\n🕑 {heure}\n{APP_URL}")
    return True
