"""The service state and its export/import format (§10, format_version 1)."""

from dataclasses import dataclass, field
from typing import Any

from .dossiers import dossier_from_json, export_dossier
from .errors import validation
from .idempotency import idempotency_from_json
from .passwords import is_valid_encoding
from .validation import is_valid_user_id

TRACK = "dossier"
FORMAT_VERSION = 1


@dataclass
class State:
    users: dict[str, dict[str, str]] = field(default_factory=dict)  # id -> user record
    emails: dict[str, str] = field(default_factory=dict)  # lowercased email -> user id
    tokens: dict[str, str] = field(default_factory=dict)  # bearer token -> user id
    dossiers: dict[str, dict[str, Any]] = field(default_factory=dict)  # domain -> dossier record
    idempotency: dict[str, dict[str, Any]] = field(default_factory=dict)  # record key -> record
    counters: dict[str, int] = field(default_factory=dict)

    def next_id(self, kind: str, prefix: str, taken) -> str:
        number = self.counters.get(kind, 0)
        while True:
            number += 1
            candidate = f"{prefix}{number}"
            if candidate not in taken:
                self.counters[kind] = number
                return candidate

    def add_user(self, user_id: str, email: str, display_name: str, password_hash: str) -> None:
        self.users[user_id] = {
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "password_hash": password_hash,
        }
        self.emails[email.lower()] = user_id

    def dossier_ids(self) -> set[str]:
        return {record["dossier_id"] for record in self.dossiers.values()}

    def to_json(self) -> dict[str, Any]:
        return {
            "users": [dict(self.users[uid]) for uid in sorted(self.users)],
            "tokens": [{"token": token, "user_id": uid} for token, uid in sorted(self.tokens.items())],
            "counters": dict(sorted(self.counters.items())),
            # A build in flight is not exported: each dossier appears as its last completed build (RL10).
            "dossiers": [export_dossier(self.dossiers[domain]) for domain in sorted(self.dossiers)],
            "idempotency": [dict(self.idempotency[key]) for key in sorted(self.idempotency)],
        }


def state_from_json(obj: Any) -> State:
    """Validate an exported state; anything malformed is 422 and builds nothing."""
    if not isinstance(obj, dict):
        raise validation("state must be an object")
    state = State()
    for entry in _list(obj, "users"):
        user_id = _str(entry, "id")
        email = _str(entry, "email")
        display_name = _str(entry, "display_name")
        password_hash = _str(entry, "password_hash")
        # RL16: exported users may be fixture users, so only the id bounds and the encoded hash are checked.
        if not is_valid_user_id(user_id) or not is_valid_encoding(password_hash):
            raise validation("state holds an invalid user")
        if user_id in state.users or email.lower() in state.emails:
            raise validation("state holds a duplicate user")
        state.add_user(user_id, email, display_name, password_hash)
    for entry in _list(obj, "tokens"):
        token = _str(entry, "token")
        user_id = _str(entry, "user_id")
        if not token or user_id not in state.users or token in state.tokens:
            raise validation("state holds an invalid token")
        state.tokens[token] = user_id
    counters = obj.get("counters", {})
    if not isinstance(counters, dict):
        raise validation("state counters must be an object")
    for name, value in counters.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise validation("state counters must be non-negative integers")
        state.counters[str(name)] = value
    for entry in _list(obj, "dossiers"):
        record = dossier_from_json(entry)
        if record["domain"] in state.dossiers or record["dossier_id"] in state.dossier_ids():
            raise validation("state holds a duplicate dossier")
        state.dossiers[record["domain"]] = record
    for entry in _list(obj, "idempotency"):
        key, record = idempotency_from_json(entry, state.users)
        if key in state.idempotency:
            raise validation("state holds a duplicate idempotency record")
        state.idempotency[key] = record
    return state


def _list(obj: dict, key: str) -> list:
    value = obj.get(key, [])
    if not isinstance(value, list):
        raise validation(f"state {key} must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise validation(f"state {key} entries must be objects")
    return value


def _str(entry: dict, key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str):
        raise validation(f"state field {key} must be a string")
    return value
