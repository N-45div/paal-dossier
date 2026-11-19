"""Export and import of the whole service state (§10); the state format is versioned."""
from __future__ import annotations

from typing import Any

from .fields import FIELD_NAMES, clean_field, unknown_fields
from .passwords import is_hash_format
from .state import Dossier, IdempotentResponse, Store, User

TRACK = "dossier"
FORMAT_VERSION = 1


class InvalidSnapshot(ValueError):
    """The submitted state is not one this service produced."""


def export_envelope(store: Store) -> dict[str, Any]:
    return {"track": TRACK, "format_version": FORMAT_VERSION, "state": export_state(store)}


def export_state(store: Store) -> dict[str, Any]:
    """Dossiers are exported as of their last completed build."""
    return {
        "users": [
            {"user_id": u.user_id, "email": u.email, "display_name": u.display_name, "password_hash": u.password_hash}
            for u in store.users.values()
        ],
        "tokens": [{"token": token, "user_id": user_id} for token, user_id in store.tokens.items()],
        "dossiers": [
            {
                "dossier_id": d.dossier_id,
                "domain": d.domain,
                "state": d.outcome or "failed",
                "researched_at": d.researched_at,
                "spent_units": d.spent_units,
                "fields": d.fields,
            }
            for d in store.dossiers.values()
        ],
        "idempotency": [
            {"user_id": u, "method": m, "path": p, "key": k, "body": r.body, "response": r.response}
            for (u, m, p, k), r in store.idempotency.items()
        ],
    }


def _expect(condition: bool) -> None:
    if not condition:
        raise InvalidSnapshot("state does not match the service format")


def _text(value: Any) -> str:
    _expect(isinstance(value, str))
    return value


def _entries(state: dict[str, Any], name: str) -> list[dict[str, Any]]:
    entries = state.get(name)
    _expect(isinstance(entries, list) and all(isinstance(e, dict) for e in entries))
    return entries


def _import_fields(raw: Any) -> dict[str, dict[str, Any]]:
    _expect(isinstance(raw, dict) and set(raw) == set(FIELD_NAMES))
    fields = {}
    for name in FIELD_NAMES:
        field = clean_field(raw[name])
        _expect(field == raw[name] or raw[name] == unknown_fields()[name])
        fields[name] = field
    return fields


def import_envelope(envelope: Any) -> Store:
    """Build a fresh store from an export envelope; raises InvalidSnapshot when it is not valid."""
    _expect(isinstance(envelope, dict))
    _expect(envelope.get("track") == TRACK)
    version = envelope.get("format_version")
    _expect(type(version) is int and version == FORMAT_VERSION)
    state = envelope.get("state")
    _expect(isinstance(state, dict))
    store = Store()
    for entry in _entries(state, "users"):
        password_hash = _text(entry.get("password_hash"))
        _expect(is_hash_format(password_hash))
        user = User(_text(entry.get("user_id")), _text(entry.get("email")), _text(entry.get("display_name")), password_hash)
        _expect(user.user_id not in store.users and user.email.lower() not in store.user_by_email)
        store.add_user(user)
    for entry in _entries(state, "tokens"):
        user_id = _text(entry.get("user_id"))
        _expect(user_id in store.users)
        store.tokens[_text(entry.get("token"))] = user_id
    for entry in _entries(state, "dossiers"):
        outcome = entry.get("state")
        _expect(outcome in ("ready", "failed"))
        researched_at = entry.get("researched_at")
        spent = entry.get("spent_units")
        _expect(researched_at is None or isinstance(researched_at, str))
        _expect(type(spent) is int and spent >= 0)
        dossier = Dossier(
            dossier_id=_text(entry.get("dossier_id")),
            domain=_text(entry.get("domain")),
            fields=_import_fields(entry.get("fields")),
            outcome=outcome,
            researched_at=researched_at,
            spent_units=spent,
        )
        _expect(dossier.domain not in store.dossiers)
        store.dossiers[dossier.domain] = dossier
    for entry in _entries(state, "idempotency"):
        identity = (_text(entry.get("user_id")), _text(entry.get("method")), _text(entry.get("path")), _text(entry.get("key")))
        _expect(identity not in store.idempotency)
        store.idempotency[identity] = IdempotentResponse(_text(entry.get("body")), entry.get("response"))
    return store
