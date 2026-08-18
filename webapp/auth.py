"""
auth.py — Hachage des mots de passe (Werkzeug / scrypt). Zéro secret en dur.
Repris du modèle calsport.
"""
from __future__ import annotations

from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(plaintext: str) -> str:
    return generate_password_hash(plaintext, method="scrypt")


def check_password(plaintext: str, hashed: str) -> bool:
    if not plaintext or not hashed:
        return False
    return check_password_hash(hashed, plaintext)
