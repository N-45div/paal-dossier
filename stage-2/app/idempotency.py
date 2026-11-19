"""Idempotency keys on the two write paths (§7, rulings L1.02 and L1.03)."""
from __future__ import annotations

import json
from typing import Any

from starlette.requests import Request

from .errors import ApiError, invalid
from .state import IdempotentResponse, Store

MAX_KEY_LENGTH = 255


def read_key(request: Request) -> str:
    key = request.headers.get("idempotency-key", "")
    if key == "":
        raise ApiError(400, "missing_idempotency_key", "Idempotency-Key header is required")
    if len(key) > MAX_KEY_LENGTH:
        raise invalid("Idempotency-Key must be 1 to 255 characters")
    return key


def canonical(body: Any) -> str:
    """Canonical text of a parsed body: key order and whitespace play no part."""
    return json.dumps(body, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def replay(store: Store, user_id: str, method: str, path: str, key: str, body: Any) -> Any | None:
    """Return the stored response for a replay, None for an unused key, or raise 409."""
    stored = store.idempotency.get((user_id, method, path, key))
    if stored is None:
        return None
    if stored.body != canonical(body):
        raise ApiError(409, "idempotency_key_reuse", "Idempotency-Key already used with a different body")
    return stored.response


def remember(store: Store, user_id: str, method: str, path: str, key: str, body: Any, response: Any) -> None:
    store.idempotency[(user_id, method, path, key)] = IdempotentResponse(canonical(body), response)
