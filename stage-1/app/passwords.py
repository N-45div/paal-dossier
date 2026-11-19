"""Password hashing with scrypt (RL12): salted, stored as one self-describing string.

Signup and login hash with SIGNUP_N. Fixture users are hashed with FIXTURE_N so that a
reset of a large fixture answers within its 10 s limit (see RL12 and the P1 handoff); the
work factor travels in the stored string, so verification is the same for both.
"""

import base64
import hashlib
import hmac
import secrets
from concurrent.futures import ThreadPoolExecutor

SIGNUP_N = 2**13
FIXTURE_N = 2**10
_MIN_N = 2**4
_MAX_N = 2**20
_MIN_R, _MAX_R = 1, 32
_MIN_P, _MAX_P = 1, 16
_MEMORY_LIMIT = 256 * 1024 * 1024  # 128 * n * r bytes; larger stored records are refused
_R = 8
_P = 1
_SALT_BYTES = 16
_DKLEN = 32
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
        maxmem=128 * n * r + 1024 * 1024,
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
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(lambda pw: hash_password(pw, FIXTURE_N), passwords))


def _parse(encoded: object) -> tuple[int, int, int, bytes, bytes] | None:
    """Parse and bound a stored hash (RL18); None for anything outside the sane ranges."""
    parts = encoded.split("$") if isinstance(encoded, str) else []
    if len(parts) != 6 or parts[0] != _PREFIX:
        return None
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        digest = base64.b64decode(parts[5], validate=True)
    except (ValueError, TypeError):
        return None
    if not (_MIN_N <= n <= _MAX_N and n & (n - 1) == 0):
        return None
    if not (_MIN_R <= r <= _MAX_R and _MIN_P <= p <= _MAX_P):
        return None
    if 128 * n * r > _MEMORY_LIMIT:
        return None
    if len(salt) != _SALT_BYTES or len(digest) != _DKLEN:
        return None
    return n, r, p, salt, digest


def is_valid_encoding(encoded: object) -> bool:
    return _parse(encoded) is not None


def verify_password(password: str, encoded: str) -> bool:
    """Check a password against a stored record; never raises, so login cannot answer 5xx."""
    parsed = _parse(encoded)
    if parsed is None:
        return False
    n, r, p, salt, digest = parsed
    try:
        candidate = _derive(password, salt, n, r, p, _DKLEN)
    except (ValueError, MemoryError, OverflowError):
        return False
    return hmac.compare_digest(candidate, digest)
