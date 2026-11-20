"""Idempotent write paths (spec §7).

A key is scoped to (user, method, raw path, key). The first request claims it and executes;
identical requests that arrive while it runs wait for that execution and then receive its
2xx reply as a 200 replay. A claim that ends without a 2xx reply is released, so the key can
be used again. A replay whose `domain` differs from the first request's is 409.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .errors import idempotency_key_reuse, missing_idempotency_key, validation_failed
from .messages import Reply, Request, json_reply
from .store import IdempotencyEntry, IdempotencyKey, Store

MAX_KEY_LENGTH = 255
HEADER = "Idempotency-Key"


def key_header(request: Request) -> str:
    """The Idempotency-Key header; absent or empty is 400."""
    key = request.headers.get(HEADER)
    if not key:
        raise missing_idempotency_key()
    return key


def check_key_length(key: str) -> str:
    if len(key) > MAX_KEY_LENGTH:
        raise validation_failed("Idempotency-Key must be 1 to 255 characters")
    return key


def domain_fingerprint(body: dict[str, Any]) -> str | None:
    """Canonical JSON of the body's `domain` value as written; None when the field is absent."""
    if "domain" not in body:
        return None
    return json.dumps(body["domain"], sort_keys=True, ensure_ascii=False)


def run_idempotent(
    store: Store,
    request: Request,
    key: str,
    fingerprint: str | None,
    operation: Callable[[], Reply],
) -> Reply:
    """Run `operation` once per key, or replay its stored 2xx reply as 200."""
    assert request.user is not None, "idempotent routes are authenticated"
    record: IdempotencyKey = (request.user.id, request.method, request.path, key)
    with store.lock:
        while True:
            entry = store.idempotency_entry(record)
            if entry is None:
                entry = IdempotencyEntry(fingerprint=fingerprint)
                store.put_idempotency(record, entry)
                break
            if entry.fingerprint != fingerprint:
                raise idempotency_key_reuse()
            if entry.reply is not None:
                return json_reply(200, entry.reply[1])
            store.changed.wait()
    reply: Reply | None = None
    try:
        reply = operation()
        return reply
    finally:
        with store.lock:
            if reply is not None and 200 <= reply.status < 300:
                entry.reply = (reply.status, reply.body)
            else:
                store.drop_idempotency(record, entry)
            store.changed.notify_all()
