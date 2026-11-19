"""Password hashing with scrypt; the hash string is self-describing."""
from __future__ import annotations

import hashlib
import hmac
import secrets

_N, _R, _P = 2**14, 8, 1


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=64 * 1024 * 1024)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _derive(password, salt, _N, _R, _P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def is_hash_format(text: str) -> bool:
    parts = text.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False
    try:
        [int(x) for x in parts[1:4]]
        bytes.fromhex(parts[4])
        bytes.fromhex(parts[5])
    except ValueError:
        return False
    return True


def verify_password(password: str, stored: str) -> bool:
    _, n, r, p, salt_hex, digest_hex = stored.split("$")
    digest = _derive(password, bytes.fromhex(salt_hex), int(n), int(r), int(p))
    return hmac.compare_digest(digest, bytes.fromhex(digest_hex))
