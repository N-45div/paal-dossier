"""Idempotency for the two write paths (§7, RL1, RL2).

A record is keyed by (user, method, path as written, key). Its identity is the request
body restricted to the known fields. A successful (2xx) answer is claimed; a 4xx never is.
"""

import json
import re
from typing import Any

from .errors import idempotency_key_reuse, missing_idempotency_key, validation

KEY_MAX = 255
RECORD_KEYS = frozenset({"user_id", "method", "path", "key", "identity", "status", "body"})
BODY_KEYS = frozenset({"dossier_id", "domain", "state"})
_REFRESH_PATH = re.compile(r"/dossiers/[^/]+/refresh")


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


def idempotency_from_json(entry: Any, users: dict) -> tuple[str, dict[str, Any]]:
    """Structural check of one exported record (RL17)."""
    if not isinstance(entry, dict) or set(entry) != RECORD_KEYS:
        raise validation("state idempotency records must have exactly the expected keys")
    user_id, method, path, key = (entry["user_id"], entry["method"], entry["path"], entry["key"])
    if not all(isinstance(v, str) for v in (user_id, method, path, key)):
        raise validation("state holds an invalid idempotency record")
    if user_id not in users or method != "POST":
        raise validation("state holds an idempotency record for an unknown user or method")
    if not (path == "/dossiers" or _REFRESH_PATH.fullmatch(path)):
        raise validation("state holds an idempotency record for an unknown path")
    if not 1 <= len(key) <= KEY_MAX:
        raise validation("state holds an invalid idempotency key")
    status = entry["status"]
    if not isinstance(status, int) or isinstance(status, bool) or not 200 <= status < 300:
        raise validation("state holds an invalid idempotency status")
    identity = entry["identity"]
    body = entry["body"]
    if not isinstance(identity, dict) or not isinstance(body, dict):
        raise validation("state holds an invalid idempotency body")
    if path == "/dossiers":
        if not set(identity) <= {"domain"} or not all(isinstance(v, str) for v in identity.values()):
            raise validation("state holds an invalid idempotency identity")
    elif identity != {}:
        raise validation("a refresh record has no identity")
    if set(body) != BODY_KEYS or not all(isinstance(v, str) for v in body.values()):
        raise validation("state holds an invalid idempotency response")
    record_key = record_key_of(user_id, method, path, key)
    return record_key, {
        "user_id": user_id,
        "method": method,
        "path": path,
        "key": key,
        "identity": dict(identity),
        "status": status,
        "body": dict(body),
    }
