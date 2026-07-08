"""Minimal session auth: pbkdf2 password hashing + opaque bearer tokens.

Good enough for a handful of trusted users; swap for Supabase/FastAPI-Users
when real multi-tenancy lands (roadmap item 1).
"""

from __future__ import annotations

import hashlib
import secrets

from fastapi import Header, HTTPException

from . import db

_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return secrets.compare_digest(digest.hex(), expected)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_user_id() -> str:
    return "u_" + secrets.token_hex(8)


def current_user(authorization: str | None = Header(None)) -> str:
    """FastAPI dependency: resolve the Bearer token to a user_id or 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Не си влязъл в профила си.")
    user_id = db.user_for_token(authorization[7:])
    if not user_id:
        raise HTTPException(401, "Сесията е изтекла — влез отново.")
    return user_id
