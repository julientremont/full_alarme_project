"""
create_user.py — Crée/renouvelle un utilisateur AEGIS.
Usage : uv run python create_user.py <username> [--admin]
Le mot de passe est demandé en interactif (jamais en argument).
"""
from __future__ import annotations

import getpass
import sys

import auth
import database as db


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    is_admin = "--admin" in sys.argv
    if not args:
        print("Usage: uv run python create_user.py <username> [--admin]")
        return 1
    username = args[0]
    db.init_db()
    pw = getpass.getpass("Mot de passe : ")
    pw2 = getpass.getpass("Confirmer : ")
    if pw != pw2 or not pw:
        print("Mots de passe différents ou vides.")
        return 1
    existing = db.get_user_by_username(username)
    if existing:
        print(f"Utilisateur '{username}' existe déjà — abandon. (Supprime-le en BDD pour recréer.)")
        return 1
    uid = db.create_user(username, auth.hash_password(pw), is_admin=is_admin)
    print(f"Utilisateur '{username}' créé (id={uid}, admin={is_admin}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
