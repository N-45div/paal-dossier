"""Idempotency keys for the two write paths (spec §7, Rul-5).

Every request runs its effect synchronously: the claim check, the effect and the record
are one step with no await between them, so concurrent identical requests cannot both
take effect. That is the whole concurrency story for this path."""

from __future__ import annotations

from collections.abc import Callable

from aiohttp import web

from app.errors import (
    ApiError,
    idempotency_key_reuse,
    json_response,
    missing_idempotency_key,
)
from app.state import IdemRecord, Store, User

MAX_KEY_LENGTH = 255


def read_key(request: web.Request) -> str:
    """The Idempotency-Key header: absent or empty is 400, too long is 422 (checked later)."""
    key = request.headers.get("Idempotency-Key", "")
    if key == "":
        raise missing_idempotency_key()
    return key


def check_key_length(key: str) -> None:
    if len(key) > MAX_KEY_LENGTH:
        raise ApiError(422, "validation_failed", "Idempotency-Key is longer than 255 characters")


def run_idempotent(
    store: Store,
    user: User,
    key: str,
    method: str,
    path: str,
    canonical: object,
    effect: Callable[[], tuple[int, dict]],
) -> web.Response:
    """Run `effect` once per (user, key, method, path) and replay its success later.

    `effect` returns (status, body) on success and raises ApiError for a 4xx; a 4xx leaves
    nothing stored, so the key stays usable. A replay with the same canonical body answers
    200 with the original body; a different canonical body is 409."""
    slot = (user.id, key, method, path)
    record = store.state.idempotency.get(slot)
    if record is not None:
        if record.canonical != canonical:
            raise idempotency_key_reuse()
        return json_response(record.body, status=200)
    status, body = effect()
    store.state.idempotency[slot] = IdemRecord(canonical=canonical, body=body)
    return json_response(body, status=status)
