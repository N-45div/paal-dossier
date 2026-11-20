"""Export and import of the whole service state (spec §10). Format version 1.

Export is an atomic read of the store under its lock. Import validates the entire document
before it touches the store, then replaces the store in one step. Neither reads the clock or
calls a provider.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from .clock import parse_rfc3339
from .dossier_model import FIELD_NAMES, Dossier, citation_from, unknown_field
from .errors import validation_failed
from .store import IdempotencyEntry, IdempotencyKey, Store, StoreState, User

TRACK = "dossier"
FORMAT_VERSION = 1


def export_document(store: Store) -> dict[str, Any]:
    with store.lock:
        state = store.state()
        return {
            "track": TRACK,
            "format_version": FORMAT_VERSION,
            "state": {
                "users": [_encode_user(user) for user in sorted(state.users, key=_id_of)],
                "tokens": [
                    {"token": token, "user_id": user_id}
                    for token, user_id in sorted(state.tokens.items())
                ],
                "dossiers": [
                    _encode_dossier(dossier)
                    for dossier in sorted(state.dossiers, key=lambda d: d.domain)
                ],
                "idempotency": [
                    _encode_record(key, entry)
                    for key, entry in sorted(state.idempotency.items())
                    if entry.reply is not None
                ],
            },
        }


def parse_document(document: Mapping[str, Any]) -> StoreState:
    if document.get("track") != TRACK or not _is_int(document.get("format_version"), FORMAT_VERSION):
        raise validation_failed("document is not a dossier export of format version 1")
    state = _mapping(document.get("state"), "state")
    users = [_decode_user(item) for item in _list(state, "users")]
    user_ids = _unique([user.id for user in users], "user id")
    _unique([user.email for user in users], "user email")

    tokens: dict[str, str] = {}
    for item in _list(state, "tokens"):
        token, user_id = _text(item, "token"), _text(item, "user_id")
        if user_id not in user_ids or token in tokens:
            raise validation_failed("token refers to an unknown user or repeats a token")
        tokens[token] = user_id

    dossiers = [_decode_dossier(item) for item in _list(state, "dossiers")]
    _unique([dossier.dossier_id for dossier in dossiers], "dossier id")
    _unique([dossier.domain for dossier in dossiers], "dossier domain")

    records: dict[IdempotencyKey, IdempotencyEntry] = {}
    for item in _list(state, "idempotency"):
        key, entry = _decode_record(item)
        if key[0] not in user_ids or key in records:
            raise validation_failed("idempotency record refers to an unknown user or repeats a key")
        records[key] = entry

    return StoreState(users=users, tokens=tokens, dossiers=dossiers, idempotency=records)


def _encode_user(user: User) -> dict[str, str]:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "password_hash": user.password_hash,
    }


def _encode_dossier(dossier: Dossier) -> dict[str, Any]:
    return {
        "dossier_id": dossier.dossier_id,
        "domain": dossier.domain,
        "state": dossier.committed_state or "failed",
        "researched_at": None if dossier.researched_at is None else dossier.researched_at.isoformat(),
        "spent_units": dossier.spent_units,
        "fields": dossier.fields,
    }


def _encode_record(key: IdempotencyKey, entry: IdempotencyEntry) -> dict[str, Any]:
    assert entry.reply is not None
    user_id, method, path, idempotency_key = key
    status, body = entry.reply
    return {
        "user_id": user_id,
        "method": method,
        "path": path,
        "key": idempotency_key,
        "fingerprint": entry.fingerprint,
        "status": status,
        "body": body,
    }


def _decode_user(item: Any) -> User:
    fields = _mapping(item, "user")
    return User(
        id=_text(fields, "id"),
        email=_text(fields, "email"),
        display_name=_text(fields, "display_name"),
        password_hash=_text(fields, "password_hash"),
    )


def _decode_dossier(item: Any) -> Dossier:
    fields = _mapping(item, "dossier")
    state = _text(fields, "state")
    if state not in ("ready", "failed"):
        raise validation_failed("dossier state must be ready or failed")
    researched_at = fields.get("researched_at")
    spent_units = fields.get("spent_units")
    if not _is_int(spent_units) or spent_units < 0:
        raise validation_failed("spent_units must be a non-negative integer")
    return Dossier(
        dossier_id=_text(fields, "dossier_id"),
        domain=_text(fields, "domain"),
        committed_state=state,
        researched_at=None if researched_at is None else _instant(researched_at),
        spent_units=spent_units,
        fields=_decode_fields(fields.get("fields")),
    )


def _decode_fields(raw: Any) -> dict[str, dict[str, Any]]:
    entries = _mapping(raw, "fields")
    decoded: dict[str, dict[str, Any]] = {}
    for name in FIELD_NAMES:
        entry = _mapping(entries.get(name), name)
        status = entry.get("status")
        citations = entry.get("citations")
        if status == "unknown":
            if entry.get("value") is not None or citations != []:
                raise validation_failed(f"unknown field {name} must have no value or citations")
            decoded[name] = unknown_field()
        elif status == "known":
            value = entry.get("value")
            if value is None or not isinstance(citations, list) or not citations:
                raise validation_failed(f"known field {name} needs a value and citations")
            clean = [citation_from(item) for item in citations]
            if any(citation is None for citation in clean):
                raise validation_failed(f"field {name} has an invalid citation")
            decoded[name] = {"value": value, "status": "known", "citations": clean}
        else:
            raise validation_failed(f"field {name} has an invalid status")
    return decoded


def _decode_record(item: Any) -> tuple[IdempotencyKey, IdempotencyEntry]:
    fields = _mapping(item, "idempotency record")
    fingerprint = fields.get("fingerprint")
    if fingerprint is not None and not isinstance(fingerprint, str):
        raise validation_failed("fingerprint must be a string or null")
    status = fields.get("status")
    if not _is_int(status) or not 200 <= status < 300 or "body" not in fields:
        raise validation_failed("idempotency record needs a 2xx status and a body")
    key: IdempotencyKey = (
        _text(fields, "user_id"),
        _text(fields, "method"),
        _text(fields, "path"),
        _text(fields, "key"),
    )
    return key, IdempotencyEntry(fingerprint=fingerprint, reply=(status, fields["body"]))


def _instant(value: Any) -> datetime:
    if not isinstance(value, str):
        raise validation_failed("researched_at must be a string or null")
    return parse_rfc3339(value)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise validation_failed(f"{name} must be an object")
    return value


def _list(obj: Mapping[str, Any], name: str) -> list[Any]:
    value = obj.get(name)
    if not isinstance(value, list):
        raise validation_failed(f"{name} must be a list")
    return value


def _text(obj: Mapping[str, Any], name: str) -> str:
    value = obj.get(name)
    if not isinstance(value, str):
        raise validation_failed(f"{name} must be a string")
    return value


def _is_int(value: Any, expected: int | None = None) -> bool:
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    return expected is None or value == expected


def _unique(values: list[str], what: str) -> set[str]:
    seen = set(values)
    if len(seen) != len(values):
        raise validation_failed(f"document repeats a {what}")
    return seen


def _id_of(user: User) -> str:
    return user.id
