"""Password hashing with scrypt (RL12): salted, stored as one self-describing string.

Signup and login hash with SIGNUP_N. Fixture users are hashed with FIXTURE_N so that a
reset of a large fixture answers within its 10 s limit (see RL12 and the P1 handoff); the
work factor travels in the stored string, so verification is the same for both.
"""

import base64
import hashlib
import hmac
import os
import secrets
from concurrent.futures import ThreadPoolExecutor

SIGNUP_N = 2**13
FIXTURE_N = 2**10
_MIN_N = 2**10
_MAX_N = 2**16
_R = 8
_P = 1
_SALT_BYTES = 16
_DKLEN = 32
_MAXMEM = 64 * 1024 * 1024
_PREFIX = "scrypt"


def _derive(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    # surrogatepass: a JSON string may hold lone surrogates; hashing must not fail on them.
    return hashlib.scrypt(
        password.encode("utf-8", "surrogatepass"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
        maxmem=_MAXMEM,
    )


def hash_password(password: str, n: int = SIGNUP_N) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = _derive(password, salt, n, _R, _P, _DKLEN)
    return "$".join(
        [
            _PREFIX,
            str(n),
            str(_R),
            str(_P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def hash_fixture_passwords(passwords: list[str]) -> list[str]:
    """Hash many fixture passwords in parallel; hashlib releases the GIL while it works."""
    workers = min(8, os.cpu_count() or 2)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda pw: hash_password(pw, FIXTURE_N), passwords))


def _parse(encoded: object) -> tuple[int, bytes, bytes] | None:
    """Parse and bound a stored hash; anything outside the work factors this service writes is None."""
    parts = encoded.split("$") if isinstance(encoded, str) else []
    if len(parts) != 6 or parts[0] != _PREFIX:
        return None
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        digest = base64.b64decode(parts[5], validate=True)
    except ValueError:
        return None
    if not (_MIN_N <= n <= _MAX_N and n & (n - 1) == 0):
        return None
    if r != _R or p != _P or len(salt) != _SALT_BYTES or len(digest) != _DKLEN:
        return None
    return n, salt, digest


def is_valid_encoding(encoded: object) -> bool:
    return _parse(encoded) is not None


def verify_password(password: str, encoded: str) -> bool:
    parsed = _parse(encoded)
    if parsed is None:
        return False
    n, salt, digest = parsed
    candidate = _derive(password, salt, n, _R, _P, _DKLEN)
    return hmac.compare_digest(candidate, digest)
