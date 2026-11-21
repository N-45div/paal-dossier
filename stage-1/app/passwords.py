"""Password hashing with scrypt (spec §6): per-user random salt, constant-time comparison."""

from __future__ import annotations

import hashlib
import hmac
import secrets

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LENGTH = 32
_SALT_LENGTH = 16


def _derive(password: str, salt: bytes) -> bytes:
    # surrogatepass: JSON may carry lone surrogates, which must not turn into a 500.
    return hashlib.scrypt(
        password.encode("utf-8", "surrogatepass"),
        salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_LENGTH,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_LENGTH)
    return f"scrypt${salt.hex()}${_derive(password, salt).hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        salt, digest = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    except ValueError:
        return False
    return hmac.compare_digest(_derive(password, salt), digest)
