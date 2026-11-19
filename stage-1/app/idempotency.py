"""Idempotency for the two write paths (§7, RL1, RL2).

A record is keyed by (user, method, path as written, key). Its identity is the request
body restricted to the known fields. A successful (2xx) answer is claimed; a 4xx never is.
"""

import json
from typing import Any

from .errors import idempotency_key_reuse, missing_idempotency_key, validation

KEY_MAX = 255


def record_key_of(user_id: str, method: str, path: str, key: str) -> str:
    return json.dumps([user_id, method, path, key], ensure_ascii=False)


def header_key(headers: dict[str, str]) -> str:
    """The Idempotency-Key header: missing or empty is 400, over 255 characters is 422."""
    key = headers.get("idempotency-key")
    if not key:
        raise missing_idempotency_key()
    if len(key) > KEY_MAX:
        raise validation("Idempotency-Key must be at most 255 characters")
    return key


def replay(state, user_id: str, method: str, path: str, key: str, identity: dict) -> dict | None:
    """The stored original body for a replay (same identity), None for a first use; 409 otherwise."""
    record = state.idempotency.get(record_key_of(user_id, method, path, key))
    if record is None:
        return None
    if record["identity"] != identity:
        raise idempotency_key_reuse()
    return dict(record["body"])


def claim(state, user_id: str, method: str, path: str, key: str, identity: dict, status: int, body: dict) -> None:
    state.idempotency[record_key_of(user_id, method, path, key)] = {
        "user_id": user_id,
        "method": method,
        "path": path,
        "key": key,
        "identity": identity,
        "status": status,
        "body": body,
    }


def idempotency_from_json(entry: dict[str, Any], users: dict) -> tuple[str, dict[str, Any]]:
    fields = {name: entry.get(name) for name in ("user_id", "method", "path", "key")}
    if not all(isinstance(value, str) for value in fields.values()):
        raise validation("state holds an invalid idempotency record")
    if fields["user_id"] not in users or not 1 <= len(fields["key"]) <= KEY_MAX:
        raise validation("state holds an invalid idempotency record")
    status = entry.get("status")
    body = entry.get("body")
    identity = entry.get("identity")
    if not isinstance(status, int) or isinstance(status, bool) or not 200 <= status < 300:
        raise validation("state holds an invalid idempotency status")
    if not isinstance(body, dict) or not isinstance(identity, dict):
        raise validation("state holds an invalid idempotency body")
    key = record_key_of(fields["user_id"], fields["method"], fields["path"], fields["key"])
    return key, {**fields, "identity": identity, "status": status, "body": body}
