"""
database.py — SQLite : utilisateurs + journal d'événements AEGIS.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.getenv("AEGIS_DB_PATH", os.path.join(os.path.dirname(__file__), "aegis.db"))


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# Onglets assignables à un utilisateur (clé interne -> libellé)
ALL_TABS = [("dashboard", "Tableau de bord"), ("controle", "Activation alarme"),
            ("cameras", "Caméras"), ("journal", "Journal"),
            ("detection", "Détection IA")]
DEFAULT_TABS = "dashboard,cameras,journal"


def init_db() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE COLLATE NOCASE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin      INTEGER NOT NULL DEFAULT 0,
                is_active     INTEGER NOT NULL DEFAULT 1,
                tabs          TEXT NOT NULL DEFAULT 'dashboard,cameras,journal',
                created_at    TEXT NOT NULL,
                last_login    TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         TEXT NOT NULL,
                category   TEXT NOT NULL,   -- alarm | sensor | system
                device     TEXT,
                event      TEXT NOT NULL,   -- armed | disarmed | open | close | online | offline | alert
                detail     TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
            CREATE TABLE IF NOT EXISTS recipients (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                kind       TEXT NOT NULL,       -- email | telegram
                value      TEXT NOT NULL,
                label      TEXT,
                active     INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_recipients ON recipients(kind, value);
            CREATE TABLE IF NOT EXISTS settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,       -- JSON
                updated_at TEXT NOT NULL
            );
            """
        )
        # Migration : ajoute les colonnes si une ancienne BDD existe déjà
        cols = {r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()}
        if "is_active" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        if "tabs" not in cols:
            c.execute(f"ALTER TABLE users ADD COLUMN tabs TEXT NOT NULL DEFAULT '{DEFAULT_TABS}'")
        if "totp_secret" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT")  # 2FA TOTP (NULL = désactivé)
        # Seed des destinataires depuis la config si la table est vide
        if c.execute("SELECT COUNT(*) n FROM recipients").fetchone()["n"] == 0:
            now = datetime.now().isoformat(timespec="seconds")
            for v in (os.getenv("MAIL_RECEPTION", "") or "").split(","):
                v = v.strip()
                if v:
                    c.execute("INSERT OR IGNORE INTO recipients (kind,value,label,active,created_at) VALUES ('email',?,?,1,?)", (v, v, now))
            for v in (os.getenv("TELEGRAM_CHAT_IDS", "") or "").split(","):
                v = v.strip()
                if v:
                    c.execute("INSERT OR IGNORE INTO recipients (kind,value,label,active,created_at) VALUES ('telegram',?,?,1,?)", (v, "Telegram", now))


# ─── Users ───────────────────────────────────────────────────────────────────

def get_user_by_username(username: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int):
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_users() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, username, is_admin, is_active, tabs, created_at, last_login "
            "FROM users ORDER BY is_admin DESC, username COLLATE NOCASE").fetchall()]


def _clean_tabs(tabs) -> str:
    valid = {k for k, _ in ALL_TABS}
    if isinstance(tabs, str):
        tabs = tabs.split(",")
    keep = [t.strip() for t in (tabs or []) if t.strip() in valid]
    return ",".join(dict.fromkeys(keep))  # dédup, ordre conservé


def create_user(username: str, password_hash: str, is_admin: bool = False,
                tabs: str | list | None = None, is_active: bool = True) -> int:
    tabs_csv = DEFAULT_TABS if tabs is None else _clean_tabs(tabs)
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_active, tabs, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (username, password_hash, int(is_admin), int(is_active), tabs_csv,
             datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def update_last_login(user_id: int) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET last_login = ? WHERE id = ?",
                  (datetime.now().isoformat(timespec="seconds"), user_id))


def set_active(user_id: int, active: bool) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET is_active = ? WHERE id = ?", (int(active), user_id))


def set_admin(user_id: int, is_admin: bool) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET is_admin = ? WHERE id = ?", (int(is_admin), user_id))


def set_tabs(user_id: int, tabs: str | list) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET tabs = ? WHERE id = ?", (_clean_tabs(tabs), user_id))


def set_password(user_id: int, password_hash: str) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def set_totp_secret(user_id: int, secret: str | None) -> None:
    """Active (secret base32) ou désactive (None) la double authentification."""
    with _conn() as c:
        c.execute("UPDATE users SET totp_secret = ? WHERE id = ?", (secret, user_id))


def delete_user(user_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))


def count_admins(active_only: bool = True) -> int:
    q = "SELECT COUNT(*) n FROM users WHERE is_admin = 1"
    if active_only:
        q += " AND is_active = 1"
    with _conn() as c:
        return c.execute(q).fetchone()["n"]


# ─── Events ──────────────────────────────────────────────────────────────────

def log_event(category: str, event: str, device: str | None = None, detail: str | None = None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO events (ts, category, device, event, detail) VALUES (?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), category, device, event, detail),
        )


def get_events(limit: int = 100, category: str | None = None):
    q = "SELECT * FROM events"
    args: list = []
    if category:
        q += " WHERE category = ?"
        args.append(category)
    q += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


# ─── Destinataires des alertes ────────────────────────────────────────────────

def list_recipients(kind: str | None = None):
    q = "SELECT * FROM recipients"
    args: list = []
    if kind:
        q += " WHERE kind = ?"
        args.append(kind)
    q += " ORDER BY kind, value"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def add_recipient(kind: str, value: str, label: str | None = None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO recipients (kind,value,label,active,created_at) VALUES (?,?,?,1,?)",
            (kind, value, label or value, datetime.now().isoformat(timespec="seconds")),
        )


def delete_recipient(rid: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM recipients WHERE id = ?", (rid,))


def set_recipient_active(rid: int, active: bool) -> None:
    with _conn() as c:
        c.execute("UPDATE recipients SET active = ? WHERE id = ?", (int(active), rid))


# ─── Réglages (clé/valeur JSON) ───────────────────────────────────────────────

def get_setting(key: str, default=None):
    with _conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (ValueError, TypeError):
        return default


def set_setting(key: str, value) -> None:
    payload = json.dumps(value)
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, payload, now),
        )
