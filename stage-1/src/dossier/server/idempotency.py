"""Idempotency keys for the two write paths (spec 7, RL1.4, RL1.5).

A claim is keyed by (user, key, method, raw path). Its body must match for a replay; an
identical request that arrives while the first is still running waits for it.
"""

import json

from dossier.server.errors import idempotency_key_reuse, missing_idempotency_key, validation
from dossier.server.model import Claim
from dossier.server.request import require_current
from dossier.server.request import Request
from dossier.server.store import Store

_WAIT_SECONDS = 0.5


def require_key_present(request: Request) -> str:
    """Absent or empty -> 400. The length rule comes after the body is parsed (RL1.4)."""
    key = request.idempotency_key
    if not key:
        raise missing_idempotency_key()
    return key


def check_key_length(key: str) -> None:
    if len(key) > 255:
        raise validation("Idempotency-Key must be 1 to 255 characters")


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def run_idempotent(store: Store, request: Request, key: str, body: str, action) -> tuple[int, dict]:
    """Run `action()` once for this claim; replays and concurrent twins get its stored body.

    The effect and the claim's completion happen in one critical section (the store lock is
    reentrant), so an export sees both or neither (R1.139). `action` returns (status, payload)
    or raises ApiError. Only a 2xx result is stored: an error removes the claim, so a waiting
    twin runs as the first use.
    """
    claim_key = (request.user_id, key, request.method, request.path)
    with store.lock:
        while True:
            require_current(store, request)
            claim = store.claims.get(claim_key)
            if claim is None:
                claim = Claim(body)
                store.claims[claim_key] = claim
                break
            if claim.body != body:
                raise idempotency_key_reuse()
            if claim.done:
                return 200, claim.payload
            store.lock.wait(timeout=_WAIT_SECONDS)
        try:
            status, payload = action()
        except BaseException:
            if store.claims.get(claim_key) is claim:
                del store.claims[claim_key]
            store.lock.notify_all()
            raise
        if store.claims.get(claim_key) is claim:
            claim.done = True
            claim.payload = payload
        store.lock.notify_all()
        return status, payload
