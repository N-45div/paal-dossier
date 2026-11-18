"""Idempotency keys for the two write paths (§7)."""
from dataclasses import dataclass
from typing import Any

from starlette.requests import Request

from app.errors import ApiError, invalid
from app.http import json_response


@dataclass
class Record:
    signature: Any
    body: dict


def key_of(request: Request) -> str:
    """The Idempotency-Key header: absent or empty 400, over 255 characters 422."""
    key = request.headers.get("idempotency-key", "")
    if not key:
        raise ApiError(400, "missing_idempotency_key", "Idempotency-Key header is required")
    if len(key) > 255:
        raise invalid("Idempotency-Key is longer than 255 characters")
    return key


def lookup(records: dict, scope: tuple, signature: Any):
    """Replay response when the key is claimed with the same request; 409 on another."""
    record = records.get(scope)
    if record is None:
        return None
    if record.signature != signature:
        raise ApiError(409, "idempotency_key_reuse", "key already used with a different body")
    return json_response(record.body, 200)
