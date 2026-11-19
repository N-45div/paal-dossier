"""Password hashing with the standard library's scrypt (spec 6)."""

import hashlib
import hmac
import secrets

_N, _R, _P = 2**12, 8, 1  # ~10 ms: the 50-in-flight budget (lead ruling); stored hashes carry their own n
_DKLEN = 32


def _derive(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    # surrogatepass keeps a lone surrogate from JSON input from raising here.
    return hashlib.scrypt(
        password.encode("utf-8", "surrogatepass"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
        maxmem=64 * 1024 * 1024,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _derive(password, salt, _N, _R, _P, _DKLEN)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = _derive(password, bytes.fromhex(salt_hex), int(n), int(r), int(p), len(digest_hex) // 2)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def is_valid_hash(stored: object) -> bool:
    """True when a stored hash has this module's format, so an import cannot plant junk."""
    if not isinstance(stored, str):
        return False
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        bytes.fromhex(parts[4])
        bytes.fromhex(parts[5])
    except ValueError:
        return False
    return n >= 2 and r >= 1 and p >= 1
