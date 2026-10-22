"""Optional password login. Off unless AUTHENTICATION is true."""

from __future__ import annotations

import hashlib
import os
import secrets

AVATARS = (
    "lemon",
    "sprout",
    "cat",
    "bunny",
    "bear",
    "fox",
    "frog",
    "panda",
    "owl",
    "chick",
    "mushroom",
    "blob",
)
SESSION_COOKIE = "caleroo_session"
SESSION_DAYS = 30
_SCRYPT_N = 2**14
_dummy: str | None = None


def authentication_enabled() -> bool:
    raw = os.environ.get("AUTHENTICATION", "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _dummy_hash() -> str:
    global _dummy
    if _dummy is None:
        _dummy = hash_password("caleroo-dummy-password")
    return _dummy


def verify_password(password: str, stored: str) -> bool:
    if len(password) > 200:
        password = "x"
    try:
        scheme, salt_hex, digest_hex = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=8, p=1, dklen=32)
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(digest, expected)


def check_password(password: str, stored: str | None) -> bool:
    return verify_password(password, stored or _dummy_hash())
