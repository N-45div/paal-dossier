"""Password hashing with scrypt (RL12): salted, stored as one self-describing string."""

import base64
import hashlib
import hmac
import secrets

_N = 2**13
_R = 8
_P = 1
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


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _derive(password, salt, _N, _R, _P, _DKLEN)
    return "$".join(
        [
            _PREFIX,
            str(_N),
            str(_R),
            str(_P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def _parse(encoded: str) -> tuple[int, int, int, bytes, bytes] | None:
    parts = encoded.split("$") if isinstance(encoded, str) else []
    if len(parts) != 6 or parts[0] != _PREFIX:
        return None
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        digest = base64.b64decode(parts[5], validate=True)
    except ValueError:
        return None
    if n < 2 or r < 1 or p < 1 or not salt or len(digest) < 16:
        return None
    return n, r, p, salt, digest


def is_valid_encoding(encoded: object) -> bool:
    return isinstance(encoded, str) and _parse(encoded) is not None


def verify_password(password: str, encoded: str) -> bool:
    parsed = _parse(encoded)
    if parsed is None:
        return False
    n, r, p, salt, digest = parsed
    candidate = _derive(password, salt, n, r, p, len(digest))
    return hmac.compare_digest(candidate, digest)
