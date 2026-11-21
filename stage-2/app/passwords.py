"""Password hashing with scrypt (spec §6). Plaintext passwords are never stored."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets

_N, _R, _P = 2**14, 8, 1
_DKLEN = 32


def _hash_sync(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN
    )


async def hash_password(password: str) -> str:
    """Return an encoded `scrypt$salt_hex$digest_hex` string, computed off the event loop."""
    salt = secrets.token_bytes(16)
    digest = await asyncio.to_thread(_hash_sync, password, salt)
    return f"scrypt${salt.hex()}${digest.hex()}"


async def verify_password(password: str, encoded: str) -> bool:
    try:
        _, salt_hex, digest_hex = encoded.split("$")
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = await asyncio.to_thread(_hash_sync, password, salt)
    return hmac.compare_digest(actual, expected)
