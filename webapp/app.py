"""
app.py — AEGIS : supervision & contrôle de l'alarme maison.
Démarrage dev : uv run flask --app app run --host 127.0.0.1 --port 5002
Modèle sécurité/design repris de calsport.
"""
from __future__ import annotations

import io
import logging
import os
import re
import secrets
import threading
import time
from datetime import date, datetime, timedelta
from functools import wraps

import pyotp
import qrcode
import qrcode.image.svg
import yaml
from dotenv import load_dotenv
import urllib.request

from flask import (
    Flask, render_template, request, session, g, flash,
    redirect, url_for, jsonify, abort, send_from_directory, Response,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

import auth
import database as db
from mqtt_state import MqttState

APP_NAME = "AEGIS"

# Secrets hors-repo (comme calsport) ; sans erreur si absent en dev.
for vault in ("/home/j.tremont/.secrets/vault.env",
              os.path.join(os.path.dirname(__file__), ".env")):
    if os.path.exists(vault):
        load_dotenv(vault)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("aegis")

app = Flask(__name__)
app.secret_key = os.getenv("AEGIS_SECRET_KEY") or os.getenv("SECRET_KEY")
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    log.warning("AEGIS_SECRET_KEY absente — clé éphémère générée (sessions invalidées au redémarrage). "
                "Définir AEGIS_SECRET_KEY en prod.")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("HTTPS", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
    # Jeton CSRF valable toute la session (évite les 400 "CSRF expired" sur un
    # tableau de bord laissé ouvert longtemps). Reste lié au cookie signé.
    WTF_CSRF_TIME_LIMIT=None,
)

limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")
csrf = CSRFProtect(app)

# ─── Données ──────────────────────────────────────────────────────────────────
with app.app_context():
    db.init_db()


def _camera_env_key(device_key: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", device_key.upper()).strip("_")


def _camera_env_value(device_key: str, field: str) -> str | None:
    value = os.getenv(f"AEGIS_CAMERA_{_camera_env_key(device_key)}_{field}")
    if value is None:
        return None
    value = value.strip()
    return value or None


def _enrich_device(device: dict) -> dict:
    item = dict(device)
    if item.get("source") != "camera":
        return item

    viewer_url = _camera_env_value(item["key"], "VIEWER_URL") or item.get("viewer_url")
    snapshot_url = _camera_env_value(item["key"], "SNAPSHOT_URL") or item.get("snapshot_url")
    viewer_mode = (
        _camera_env_value(item["key"], "VIEWER_MODE")
        or item.get("viewer_mode")
        or "iframe"
    ).lower()
    if viewer_mode not in {"iframe", "image", "video"}:
        viewer_mode = "iframe"

    item["viewer_url"] = viewer_url or ""
    item["snapshot_url"] = snapshot_url or ""
    item["viewer_mode"] = viewer_mode
    item["transport"] = (
        _camera_env_value(item["key"], "TRANSPORT")
        or item.get("transport")
        or "RTSP -> HLS/WebRTC"
    )
    item["note"] = _camera_env_value(item["key"], "NOTE") or item.get("note") or ""
    item["configured"] = bool(item["viewer_url"] or item["snapshot_url"])
    return item


def load_registry() -> list[dict]:
    with open(os.path.join(os.path.dirname(__file__), "devices.yaml")) as f:
        groups = yaml.safe_load(f)["groups"]

    return [
        {
            **group,
            "devices": [_enrich_device(device) for device in group.get("devices", [])],
        }
        for group in groups
    ]


REGISTRY = load_registry()

state = MqttState(base_topic=os.getenv("MQTT_BASE_TOPIC", "zigbee2mqtt"))
state.start(
    host=os.getenv("MQTT_HOST", "127.0.0.1"),
    port=int(os.getenv("MQTT_PORT", "1883")),
    username=os.getenv("MQTT_USERNAME") or None,
    password=os.getenv("MQTT_PASSWORD") or None,
)


# ─── Moniteur santé (alertes système via aegis/notify) ─────────────────────────
_health: dict = {}
_battery_alerted: set = set()


def _notify(title, line, key):
    state.publish("aegis/notify", {"title": title, "line": line, "key": key, "force": True})


def health_monitor():
    """Transitions santé (bridge, batterie, prise) ET anti-sabotage quand ARMÉ :
    la perte du coordinateur ou des routeurs/prises Zigbee = brouillage/coupure
    probable → alerte immédiate (au lieu d'attendre le timeout capteur de 3 h)."""
    time.sleep(25)  # laisser arriver les états retenus au démarrage
    while True:
        try:
            armed = state.alarm_state().get("state") == "armed"
            online = state.connected and state.bridge_online
            prev_bridge = _health.get("bridge")
            if prev_bridge is not None and online != prev_bridge:
                if online:
                    _notify("Bridge Zigbee rétabli", "La supervision des capteurs est de nouveau active.", "bridge")
                elif armed:
                    _notify("🚨 Sabotage possible",
                            "Coordinateur Zigbee hors-ligne ALORS QUE L'ALARME EST ARMÉE (brouillage / coupure ?).",
                            "tamper-bridge")
                else:
                    _notify("Bridge Zigbee hors-ligne", "⚠️ Plus de supervision des capteurs Zigbee (coordinateur injoignable).", "bridge")
            _health["bridge"] = online

            routers = []
            routers_off = 0
            for grp in REGISTRY:
                for dev in grp["devices"]:
                    st = state.device_status(dev)
                    key = dev["key"]
                    label = dev.get("label", key)
                    src, kind = dev.get("source"), dev.get("kind")
                    bat = (st.get("extra") or {}).get("battery")
                    if isinstance(bat, (int, float)):
                        if bat < 15 and key not in _battery_alerted:
                            _battery_alerted.add(key)
                            _notify("Batterie faible", f"{label} : batterie à {bat}%. À remplacer bientôt.", f"bat:{key}")
                        elif bat >= 20:
                            _battery_alerted.discard(key)
                    # Routeurs Zigbee (secteur) : perte = sabotage/brouillage si armé
                    if src == "zigbee" and kind == "router":
                        off = st.get("status") == "offline"
                        routers.append(key)
                        routers_off += int(off)
                        if _health.get(f"router:{key}") is False and off and armed:
                            _notify("🚨 Sabotage possible",
                                    f"Routeur « {label} » injoignable alors que l'alarme est armée (brouillage ?).",
                                    f"tamper:{key}")
                        _health[f"router:{key}"] = off
                    if src == "plug":
                        off = st.get("status") == "offline"
                        prev = _health.get(f"plug:{key}")
                        if prev is not None and off != prev:
                            if off and armed:
                                _notify("🚨 Sabotage possible",
                                        f"Prise « {label} » coupée alors que l'alarme est armée.", f"tamper:{key}")
                            elif off:
                                _notify("Prise injoignable", f"{label} ne répond plus (réseau ?).", f"plug:{key}")
                            else:
                                _notify("Prise rétablie", f"{label} est de nouveau joignable.", f"plug:{key}")
                        _health[f"plug:{key}"] = off

            # Brouillage : tous les routeurs Zigbee tombent en même temps (armé)
            jam = bool(routers) and routers_off == len(routers)
            if armed and jam and not _health.get("jam"):
                _notify("🚨 Brouillage Zigbee suspecté",
                        "Tous les routeurs Zigbee sont injoignables simultanément (alarme armée).", "tamper-jam")
            _health["jam"] = jam
        except Exception:
            pass
        time.sleep(45)


threading.Thread(target=health_monitor, daemon=True).start()


# ─── Auth & permissions ───────────────────────────────────────────────────────
ALL_TABS = db.ALL_TABS                     # [(key, label), ...]
TAB_ENDPOINT = {"dashboard": "dashboard", "cameras": "cameras", "journal": "journal",
                "controle": "controle", "detection": "detection"}


def user_tabs(user) -> list[str]:
    """Onglets visibles. Admin = tous."""
    if not user:
        return []
    if user.get("is_admin"):
        return [k for k, _ in ALL_TABS]
    return [t for t in (user.get("tabs") or "").split(",") if t]


def landing_url(user):
    if user.get("is_admin"):
        return url_for("dashboard")
    for k, _ in ALL_TABS:
        if k in user_tabs(user):
            return url_for(TAB_ENDPOINT[k])
    return None


@app.before_request
def load_user():
    """Charge l'utilisateur depuis la BDD à chaque requête.
    Applique immédiatement un blocage/suppression (déconnexion)."""
    g.user = None
    uid = session.get("user_id")
    if uid is not None:
        u = db.get_user_by_id(uid)
        if not u or not u["is_active"]:
            session.clear()           # bloqué ou supprimé → session invalidée
        else:
            g.user = u


@app.before_request
def enforce_2fa():
    """2FA OBLIGATOIRE : un compte connecté sans double authentification est
    bloqué sur la page d'activation tant qu'il ne l'a pas configurée.
    (Les appels API/static/déconnexion passent pour ne pas casser la page.)"""
    u = getattr(g, "user", None)
    if not u or u["totp_secret"]:
        return
    ep = request.endpoint or ""
    # « controle » = page Activation/désarmement : TOUJOURS accessible (urgence :
    # pouvoir désarmer même sans 2FA encore configurée). Le reste (caméras,
    # journal, admin…) reste bloqué tant que la 2FA n'est pas activée.
    if (ep in ("two_factor_setup", "logout", "static", "healthz", "controle")
            or ep.startswith("api_")):
        return
    return redirect(url_for("two_factor_setup"))


def _asset_version() -> str:
    """Empreinte du CSS (mtime) pour forcer navigateur + Cloudflare à recharger."""
    try:
        return str(int(os.path.getmtime(os.path.join(app.static_folder, "style.css"))))
    except OSError:
        return "0"


@app.context_processor
def inject_nav():
    u = getattr(g, "user", None)
    home_url = (landing_url(u) or url_for("logout")) if u else url_for("login")
    icons_sprite = url_for("static", filename="aegis-icons.svg")
    return {"app_name": APP_NAME,
            "asset_v": _asset_version(),
            "username": u["username"] if u else "",
            "nav_tabs": user_tabs(u),
            "is_admin": bool(u and u["is_admin"]),
            "is_authenticated": bool(u),
            "home_url": home_url,
            "icons_sprite": icons_sprite}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not getattr(g, "user", None):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def require_tab(tab):
    def deco(f):
        @wraps(f)
        def w(*args, **kwargs):
            if not getattr(g, "user", None):
                return redirect(url_for("login"))
            if tab not in user_tabs(g.user):
                abort(403)
            return f(*args, **kwargs)
        return w
    return deco


def admin_required(f):
    @wraps(f)
    def w(*args, **kwargs):
        if not getattr(g, "user", None):
            return redirect(url_for("login"))
        if not g.user["is_admin"]:
            abort(403)
        return f(*args, **kwargs)
    return w


def ctx(active):
    return {"active_page": active}


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if getattr(g, "user", None):
        return redirect(landing_url(g.user) or url_for("logout"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            error = "Identifiant et mot de passe requis."
        else:
            user = db.get_user_by_username(username)
            if user and auth.check_password(password, user["password_hash"]):
                if not user["is_active"]:
                    error = "Compte bloqué. Contactez l'administrateur."
                else:
                    # Promotion admin via env ADMIN_USERS (au cas où)
                    admin_names = {n.strip().lower() for n in os.environ.get("ADMIN_USERS", "").split(",") if n.strip()}
                    if not user["is_admin"] and user["username"].lower() in admin_names:
                        db.set_admin(user["id"], True)
                    # 2FA activée → 2e facteur exigé avant d'ouvrir la session
                    if user["totp_secret"]:
                        session.clear()
                        session["pending_2fa"] = user["id"]
                        session["pending_2fa_ts"] = time.time()
                        return redirect(url_for("two_factor"))
                    session.permanent = True
                    session["user_id"] = user["id"]
                    db.update_last_login(user["id"])
                    user = db.get_user_by_id(user["id"])
                    dest = landing_url(user)
                    if not dest:
                        session.clear()
                        error = "Aucun onglet autorisé pour ce compte. Contactez l'administrateur."
                    else:
                        return redirect(dest)
            elif not error:
                error = "Identifiant ou mot de passe incorrect."
    return render_template("login.html", error=error, app_name=APP_NAME)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── Double authentification (TOTP) ───────────────────────────────────────────
def _qr_svg(uri: str) -> str:
    """QR d'enrôlement en SVG inline (aucune dépendance image binaire)."""
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=9, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


@app.route("/2fa", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def two_factor():
    """2e facteur exigé après le mot de passe quand la 2FA est active."""
    uid = session.get("pending_2fa")
    ts = session.get("pending_2fa_ts", 0)
    if not uid or (time.time() - ts) > 300:           # fenêtre de 5 min
        session.pop("pending_2fa", None)
        session.pop("pending_2fa_ts", None)
        return redirect(url_for("login"))
    user = db.get_user_by_id(uid)
    if not user or not user["is_active"] or not user["totp_secret"]:
        session.clear()
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        code = re.sub(r"\s+", "", request.form.get("code", ""))
        if code and pyotp.TOTP(user["totp_secret"]).verify(code, valid_window=2):
            session.pop("pending_2fa", None)
            session.pop("pending_2fa_ts", None)
            session.permanent = True
            session["user_id"] = user["id"]
            db.update_last_login(user["id"])
            return redirect(landing_url(user) or url_for("logout"))
        error = "Code incorrect. Réessayez."
    return render_template("two_factor.html", error=error, app_name=APP_NAME)


@app.route("/2fa/setup", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per minute")
def two_factor_setup():
    """Activation / désactivation de la 2FA pour le compte connecté."""
    user = g.user
    has = bool(user["totp_secret"])
    if request.method == "POST":
        action = request.form.get("action")
        code = re.sub(r"\s+", "", request.form.get("code", ""))
        if action == "enable" and not has:
            secret = session.get("totp_provisional")
            if not secret:
                flash("Session expirée — recharge la page et rescanne le QR.", "error")
            elif code and pyotp.TOTP(secret).verify(code, valid_window=2):
                db.set_totp_secret(user["id"], secret)
                session.pop("totp_provisional", None)
                flash("Double authentification activée.", "ok")
            else:
                log.warning("2FA activation refusée (%s) : secret_présent=%s code_len=%d",
                            user["username"], bool(secret), len(code))
                flash("Code refusé. Supprime toute ancienne entrée « AEGIS » de ton app, "
                      "rescanne le QR ci-dessous, puis saisis le code affiché.", "error")
        elif action == "disable" and has:
            if code and pyotp.TOTP(user["totp_secret"]).verify(code, valid_window=2):
                db.set_totp_secret(user["id"], None)
                flash("Double authentification désactivée.", "ok")
            else:
                flash("Code incorrect.", "error")
        return redirect(url_for("two_factor_setup"))

    qr_svg = secret = None
    if not has:
        secret = session.get("totp_provisional") or pyotp.random_base32()
        session["totp_provisional"] = secret
        uri = pyotp.TOTP(secret).provisioning_uri(name=user["username"], issuer_name=APP_NAME)
        qr_svg = _qr_svg(uri)
    return render_template("two_factor_setup.html", has_2fa=has, secret=secret,
                           qr_svg=qr_svg, **ctx("2fa"))


# ─── Pages ────────────────────────────────────────────────────────────────────
@app.route("/")
@require_tab("dashboard")
def dashboard():
    return render_template("dashboard.html", **ctx("dashboard"))


@app.route("/cameras")
@require_tab("cameras")
def cameras():
    cams = []
    for grp in REGISTRY:
        if grp["id"] == "cameras":
            cams = grp["devices"]
    return render_template("cameras.html", cameras=cams, **ctx("cameras"))


@app.route("/journal")
@require_tab("journal")
def journal():
    events = db.get_events(limit=200)
    return render_template("journal.html", events=events, **ctx("journal"))


@app.route("/controle")
@require_tab("controle")
def controle():
    return render_template("controle.html", **ctx("controle"))


@app.route("/detection")
@require_tab("detection")
def detection():
    return render_template("detection.html", objects=OBJECT_CATALOG,
                           config=detection_config(), **ctx("detection"))


# ─── Administration (gestion des comptes) ─────────────────────────────────────
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.route("/admin")
@admin_required
def admin():
    users = db.list_users()
    for u in users:
        u["tab_list"] = [t for t in (u["tabs"] or "").split(",") if t]
    recipients = db.list_recipients()
    return render_template("admin.html", users=users, all_tabs=ALL_TABS,
                           me=g.user["id"], recipients=recipients, **ctx("admin"))


@app.route("/admin/recipients/add", methods=["POST"])
@admin_required
def admin_recipient_add():
    email = request.form.get("email", "").strip()
    if not EMAIL_RE.match(email):
        flash("Adresse e-mail invalide.", "error")
    else:
        db.add_recipient("email", email, email)
        flash(f"Destinataire « {email} » ajouté.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/recipients/<int:rid>/delete", methods=["POST"])
@admin_required
def admin_recipient_delete(rid):
    db.delete_recipient(rid)
    flash("Destinataire retiré.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/create", methods=["POST"])
@admin_required
@limiter.limit("20 per minute")
def admin_create():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    is_admin = request.form.get("is_admin") == "on"
    tabs = request.form.getlist("tabs")
    if not username or not password:
        flash("Identifiant et mot de passe requis.", "error")
    elif len(password) < 8:
        flash("Mot de passe : 8 caractères minimum.", "error")
    elif db.get_user_by_username(username):
        flash(f"L'utilisateur « {username} » existe déjà.", "error")
    else:
        db.create_user(username, auth.hash_password(password), is_admin=is_admin, tabs=tabs)
        flash(f"Compte « {username} » créé.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/<int:uid>/update", methods=["POST"])
@admin_required
def admin_update(uid):
    target = db.get_user_by_id(uid)
    if not target:
        abort(404)
    action = request.form.get("action")

    if action == "tabs":
        db.set_tabs(uid, request.form.getlist("tabs"))
        flash(f"Onglets de « {target['username']} » mis à jour.", "ok")

    elif action == "toggle_active":
        new_active = not target["is_active"]
        if not new_active and target["is_admin"] and db.count_admins(active_only=True) <= 1:
            flash("Impossible de bloquer le dernier admin actif.", "error")
        else:
            db.set_active(uid, new_active)
            flash(f"« {target['username']} » {'débloqué' if new_active else 'bloqué'}.", "ok")

    elif action == "toggle_admin":
        new_admin = not target["is_admin"]
        if not new_admin and db.count_admins(active_only=False) <= 1:
            flash("Impossible de retirer le dernier admin.", "error")
        else:
            db.set_admin(uid, new_admin)
            flash(f"« {target['username']} » {'promu admin' if new_admin else 'rétrogradé'}.", "ok")

    elif action == "password":
        pw = request.form.get("password", "")
        if len(pw) < 8:
            flash("Mot de passe : 8 caractères minimum.", "error")
        else:
            db.set_password(uid, auth.hash_password(pw))
            flash(f"Mot de passe de « {target['username']} » réinitialisé.", "ok")

    elif action == "delete":
        if uid == g.user["id"]:
            flash("Vous ne pouvez pas supprimer votre propre compte.", "error")
        elif target["is_admin"] and db.count_admins(active_only=False) <= 1:
            flash("Impossible de supprimer le dernier admin.", "error")
        else:
            db.delete_user(uid)
            flash(f"Compte « {target['username']} » supprimé.", "ok")

    return redirect(url_for("admin"))


# ─── API ──────────────────────────────────────────────────────────────────────
@app.route("/api/state")
@login_required
def api_state():
    groups = []
    for grp in REGISTRY:
        items = [state.device_status(d) for d in grp["devices"]]
        groups.append({"id": grp["id"], "label": grp["label"], "devices": items})
    summary = {"mqtt": state.connected, "bridge": state.bridge_online,
               "alarm": state.alarm_state()}
    return jsonify({"groups": groups, "summary": summary})


@app.route("/api/events")
@login_required
def api_events():
    return jsonify(db.get_events(limit=int(request.args.get("limit", 100))))


CAPTURES_DIR = os.getenv("CAPTURES_DIR", os.path.join(os.path.dirname(__file__), "captures"))


@app.route("/api/captures")
@require_tab("cameras")
def api_captures():
    """Liste les dernières captures locales (nom + horodatage)."""
    limit = int(request.args.get("limit", 24))
    items = []
    try:
        for name in os.listdir(CAPTURES_DIR):
            if name.lower().endswith(".jpg"):
                p = os.path.join(CAPTURES_DIR, name)
                items.append({"name": name, "ts": os.path.getmtime(p)})
    except FileNotFoundError:
        pass
    items.sort(key=lambda x: x["ts"], reverse=True)
    return jsonify(items[:limit])


@app.route("/captures/<path:filename>")
@require_tab("cameras")
def capture_file(filename):
    return send_from_directory(CAPTURES_DIR, filename)


# ─── Détection IA (réglages YOLO) ─────────────────────────────────────────────
# Les réglages sont persistés en base puis diffusés à l'orchestrateur (retenu)
# sur aegis/detection/config. Les statistiques sont dérivées des captures YOLO
# (nom de fichier : « <Pièce>_<Objet>_<AAAA-MM-JJ>_<HH-MM-SS>.jpg »).
DETECTION_TOPIC = "aegis/detection/config"
OBJECT_CATALOG = [
    {"key": "person",   "label": "Personne", "cls": 0},
    {"key": "knife",    "label": "Couteau",  "cls": 43},
    {"key": "scissors", "label": "Ciseaux",  "cls": 76},
    {"key": "bat",      "label": "Batte",    "cls": 34},
]
OBJECT_BY_KEY = {o["key"]: o for o in OBJECT_CATALOG}
FR_TO_KEY = {o["label"]: o["key"] for o in OBJECT_CATALOG}
DEFAULT_DETECTION = {
    "enabled": True,
    "confidence": 0.45,         # seuil de confiance YOLO (0.8 ratait les passages rapides)
    "motion_sensitivity": 10000,  # seuil de différence d'images (veille)
    "objects": {o["key"]: True for o in OBJECT_CATALOG},
}
CONF_MIN, CONF_MAX = 0.10, 0.95
MOTION_MIN, MOTION_MAX = 2000, 60000
MODEL_FILE = os.path.join(os.path.dirname(__file__), "..", "orchestrator", "models", "yolov8n.pt")


def detection_config() -> dict:
    """Config effective : défauts fusionnés avec les réglages persistés."""
    cfg = {**DEFAULT_DETECTION, "objects": dict(DEFAULT_DETECTION["objects"])}
    stored = db.get_setting("detection", {})
    if isinstance(stored, dict):
        if "enabled" in stored:
            cfg["enabled"] = bool(stored["enabled"])
        try:
            if "confidence" in stored:
                cfg["confidence"] = round(min(CONF_MAX, max(CONF_MIN, float(stored["confidence"]))), 2)
            if "motion_sensitivity" in stored:
                cfg["motion_sensitivity"] = int(min(MOTION_MAX, max(MOTION_MIN, int(stored["motion_sensitivity"]))))
        except (TypeError, ValueError):
            pass
        if isinstance(stored.get("objects"), dict):
            for k in cfg["objects"]:
                if k in stored["objects"]:
                    cfg["objects"][k] = bool(stored["objects"][k])
    return cfg


def publish_detection(cfg: dict) -> None:
    classes = [OBJECT_BY_KEY[k]["cls"] for k, on in cfg["objects"].items() if on]
    state.publish(DETECTION_TOPIC, {
        "enabled": bool(cfg["enabled"]),
        "confidence": cfg["confidence"],
        "motion_sensitivity": cfg["motion_sensitivity"],
        "classes": classes,
        "objects": cfg["objects"],
    }, retain=True)


def detection_stats() -> dict:
    """Statistiques de détection dérivées des captures (7 derniers jours)."""
    cats = {o["key"]: 0 for o in OBJECT_CATALOG}
    today = date.today()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    series = {d.isoformat(): 0 for d in days}
    today_count = 0
    last = None
    try:
        entries = list(os.scandir(CAPTURES_DIR))
    except FileNotFoundError:
        entries = []
    for e in entries:
        if not e.name.lower().endswith(".jpg"):
            continue
        try:
            ts = e.stat().st_mtime
        except OSError:
            continue
        d = datetime.fromtimestamp(ts).date()
        obj = next((key for fr, key in FR_TO_KEY.items() if f"_{fr}_" in e.name), None)
        if d == today:
            today_count += 1
        iso = d.isoformat()
        if iso in series:
            series[iso] += 1
            if obj:
                cats[obj] += 1
        if last is None or ts > last["ts"]:
            last = {"ts": ts, "object": obj}
    last_out = None
    if last:
        lbl = OBJECT_BY_KEY.get(last["object"], {}).get("label") if last["object"] else None
        last_out = {"iso": datetime.fromtimestamp(last["ts"]).isoformat(), "label": lbl}
    return {
        "today": today_count,
        "total_7d": sum(series.values()),
        "by_object": cats,
        "series": [{"day": d.isoformat(), "label": d.strftime("%a"),
                    "count": series[d.isoformat()]} for d in days],
        "last": last_out,
    }


def model_status() -> dict:
    return {"name": "YOLOv8n", "present": os.path.exists(MODEL_FILE),
            "armed": state.alarm_state().get("state") == "armed"}


@app.route("/api/detection", methods=["GET", "POST"])
@require_tab("detection")
@limiter.limit("60 per minute")
def api_detection():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        cfg = detection_config()
        if "enabled" in data:
            cfg["enabled"] = bool(data["enabled"])
        if "confidence" in data:
            try:
                cfg["confidence"] = round(min(CONF_MAX, max(CONF_MIN, float(data["confidence"]))), 2)
            except (TypeError, ValueError):
                return jsonify({"error": "confiance invalide"}), 400
        if "motion_sensitivity" in data:
            try:
                cfg["motion_sensitivity"] = int(min(MOTION_MAX, max(MOTION_MIN, int(data["motion_sensitivity"]))))
            except (TypeError, ValueError):
                return jsonify({"error": "seuil invalide"}), 400
        if isinstance(data.get("objects"), dict):
            for k in cfg["objects"]:
                if k in data["objects"]:
                    cfg["objects"][k] = bool(data["objects"][k])
        if not any(cfg["objects"].values()):
            return jsonify({"error": "Au moins un objet doit rester surveillé."}), 400
        db.set_setting("detection", cfg)
        publish_detection(cfg)
        log.info("Réglages détection mis à jour par %s", g.user["username"])
        return jsonify({"ok": True, "config": cfg})
    return jsonify({"config": detection_config(), "stats": detection_stats(),
                    "model": model_status()})


def _sync_detection():
    """Diffuse la config persistée à l'orchestrateur au démarrage (retenu)."""
    time.sleep(6)  # laisser le lien MQTT s'établir
    try:
        with app.app_context():
            publish_detection(detection_config())
    except Exception:
        pass


threading.Thread(target=_sync_detection, daemon=True).start()


GO2RTC_URL = os.getenv("GO2RTC_URL", "http://127.0.0.1:1984")
REAL_CAM_KEYS = {d["key"] for grp in REGISTRY if grp["id"] == "cameras"
                 for d in grp["devices"] if d.get("real")}


@app.route("/cameras/live/<key>")
@require_tab("cameras")
def camera_live(key):
    """Flux vidéo en direct (proxy go2rtc), uniquement quand l'alarme est armée
    (désarmé = caméras en privacy, ne filment pas)."""
    if key not in REAL_CAM_KEYS:
        abort(404)
    # Désarmé = caméras hors tension (prises Tapo coupées = confidentialité) → pas de flux.
    if state.alarm_state().get("state") != "armed":
        abort(409)
    # Snapshot JPEG unique : le flux MJPEG de go2rtc ne produit rien ici, mais
    # frame.jpeg marche partout. Le navigateur rafraîchit l'image ~1x/s → un
    # pseudo-direct FIABLE sur tous les mobiles (iOS/Android).
    url = f"{GO2RTC_URL}/api/frame.jpeg?src={key}"
    try:
        with urllib.request.urlopen(url, timeout=8) as up:
            data = up.read()
    except Exception:
        abort(502)
    return Response(data, mimetype="image/jpeg",
                    headers={"Cache-Control": "no-store, max-age=0"})


PLUG_KEYS = {d["key"] for grp in REGISTRY if grp["id"] == "prises" for d in grp["devices"]}


@app.route("/api/plug/<key>/set", methods=["POST"])
@require_tab("controle")
@limiter.limit("60 per minute")
def api_plug_set(key):
    if key not in PLUG_KEYS:
        return jsonify({"error": "prise inconnue"}), 404
    data = request.get_json(silent=True) or request.form
    on = str(data.get("on")).lower() in ("1", "true", "on", "yes")
    state.publish(f"aegis/plug/{key}/set", {"on": on})
    log.info("Prise %s -> %s (par %s)", key, "ON" if on else "OFF", g.user["username"])
    return jsonify({"ok": True, "key": key, "on": on})


@app.route("/api/siren", methods=["GET", "POST"])
@require_tab("controle")
@limiter.limit("30 per minute")
def api_siren():
    """GET : état sirène (temp/humidité/volume/sonnerie). POST : réglages."""
    if request.method == "GET":
        with state._lock:
            return jsonify(dict(state.siren_state))
    data = request.get_json(silent=True) or request.form
    cmd: dict = {}
    try:
        if "volume" in data:
            cmd["volume"] = max(0, min(2, int(data["volume"])))
        if "ringtone" in data:
            cmd["ringtone"] = max(1, min(12, int(data["ringtone"])))
        if "duration" in data:
            cmd["duration"] = max(0, min(1800, int(data["duration"])))
    except (TypeError, ValueError):
        return jsonify({"error": "valeur invalide"}), 400
    if str(data.get("test", "")).lower() in ("1", "true", "on", "yes"):
        cmd["test"] = True
    if "on" in data:
        cmd["on"] = str(data.get("on")).lower() in ("1", "true", "on", "yes")
    if not cmd:
        return jsonify({"error": "aucune commande"}), 400
    state.publish("aegis/siren/set", cmd)
    log.info("Sirène : %s (par %s)", cmd, g.user["username"])
    return jsonify({"ok": True, "sent": cmd})


@app.route("/api/alarm")
@require_tab("controle")
def api_alarm():
    return jsonify(state.alarm_state())


@app.route("/api/alarm/set", methods=["POST"])
@require_tab("controle")
@limiter.limit("30 per minute")
def api_alarm_set():
    data = request.get_json(silent=True) or request.form
    action = (data.get("action") or "").lower()
    if action not in ("arm", "disarm"):
        return jsonify({"error": "action invalide"}), 400
    desired = "armed" if action == "arm" else "disarmed"
    state.publish("aegis/alarm/set",
                  {"state": desired, "by": g.user["username"]}, retain=True)
    if action == "disarm":
        # Coupe-sirène DIRECT : le service sirène (léger, réactif) reçoit l'ordre
        # même si l'orchestrateur est saturé/injoignable. Filet de sécurité désarmement.
        state.publish("aegis/siren/set", {"on": False})
    log.info("Alarme %s demandée par %s", desired, g.user["username"])
    return jsonify({"ok": True, "requested": desired})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "mqtt": state.connected})


# ─── Erreurs ──────────────────────────────────────────────────────────────────
@app.errorhandler(403)
def err_403(e):
    return render_template("error.html", code=403,
                           title="Accès refusé",
                           msg="Cet écran n'est pas autorisé pour votre session.",
                           action_label="Retour au tableau de bord",
                           action_url=landing_url(g.user) if getattr(g, "user", None) else url_for("login")), 403


@app.errorhandler(404)
def err_404(e):
    return render_template("error.html", code=404,
                           title="Page introuvable",
                           msg="La ressource demandée n'existe pas ou n'est plus disponible.",
                           action_label="Retour au tableau de bord",
                           action_url=landing_url(g.user) if getattr(g, "user", None) else url_for("login")), 404


@app.errorhandler(500)
def err_500(e):
    log.exception("erreur interne AEGIS: %s", e)
    return render_template("error.html", code=500,
                           title="Service momentanément indisponible",
                           msg="La console AEGIS a rencontré une erreur interne. Réessayez dans un instant.",
                           action_label="Retour à la console",
                           action_url=landing_url(g.user) if getattr(g, "user", None) else url_for("login")), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002)
