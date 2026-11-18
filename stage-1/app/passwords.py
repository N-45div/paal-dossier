"""Password hashing with scrypt, in a versioned self-describing format."""
import asyncio
import hashlib
import hmac
import os
from concurrent.futures import ThreadPoolExecutor

_N, _R, _P = 2 ** 14, 8, 1

# Hashing is CPU bound: two workers leave one of the two vCPUs to the request loop.
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scrypt")


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8", "surrogatepass"), salt=salt,
                          n=n, r=r, p=p, maxmem=128 * 1024 * 1024)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = _derive(password, salt, _N, _R, _P)
    return f"scrypt1${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        actual = _derive(password, bytes.fromhex(salt), int(n), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(actual, bytes.fromhex(digest))


async def hash_password_async(password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(_pool, hash_password, password)


async def verify_password_async(password: str, stored: str) -> bool:
    return await asyncio.get_running_loop().run_in_executor(_pool, verify_password, password, stored)
