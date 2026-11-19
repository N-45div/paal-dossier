"""The service state and its export/import format (§10, format_version 1).

Import is structural (RL17): every section must be present with its type, every entry
must have exactly the keys this service writes, ids are unique, counters cover the ids
already issued, and each dossier, token and idempotency record is checked for shape.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from .dossiers import dossier_from_json, export_dossier
from .errors import validation
from .idempotency import idempotency_from_json
from .passwords import is_valid_encoding
from .validation import is_valid_user_id

TRACK = "dossier"
FORMAT_VERSION = 1
SECTIONS = ("counters", "dossiers", "idempotency", "tokens", "users")
USER_KEYS = frozenset({"id", "email", "display_name", "password_hash"})
TOKEN_KEYS = frozenset({"token", "user_id"})
COUNTER_PREFIXES = {"user": "u_", "dossier": "d_"}
MAX_COUNTER = 10**12
_CANONICAL = re.compile(r"[1-9][0-9]{0,11}")


def canonical_number(kind: str, identifier: str) -> int | None:
    """The number an id was issued with, for ids of the form prefix + canonical decimal."""
    prefix = COUNTER_PREFIXES[kind]
    if not identifier.startswith(prefix):
        return None
    rest = identifier[len(prefix):]
    return int(rest) if _CANONICAL.fullmatch(rest) else None


@dataclass
class State:
    users: dict[str, dict[str, str]] = field(default_factory=dict)  # id -> user record
    emails: dict[str, str] = field(default_factory=dict)  # lowercased email -> user id
    tokens: dict[str, str] = field(default_factory=dict)  # bearer token -> user id
    dossiers: dict[str, dict[str, Any]] = field(default_factory=dict)  # domain -> dossier record
    idempotency: dict[str, dict[str, Any]] = field(default_factory=dict)  # record key -> record
    counters: dict[str, int] = field(default_factory=dict)

    def next_id(self, kind: str, taken) -> str:
        number = self.counters.get(kind, 0)
        prefix = COUNTER_PREFIXES[kind]
        while True:
            number += 1
            candidate = f"{prefix}{number}"
            if candidate not in taken:
                self.counters[kind] = number
                return candidate

    def reserve(self, kind: str, identifier: str) -> None:
        """Raise the counter to cover an id that was not issued by the counter (a fixture id)."""
        number = canonical_number(kind, identifier)
        if number is not None and number > self.counters.get(kind, 0):
            self.counters[kind] = number

    def add_user(self, user_id: str, email: str, display_name: str, password_hash: str, *, reserve: bool = True) -> None:
        self.users[user_id] = {
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "password_hash": password_hash,
        }
        self.emails[email.lower()] = user_id
        if reserve:
            self.reserve("user", user_id)

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
    """Validate an exported state structurally; anything malformed is 422 and builds nothing."""
    if not isinstance(obj, dict):
        raise validation("state must be an object")
    if set(obj) != set(SECTIONS):
        raise validation("state must hold exactly the sections counters, dossiers, idempotency, tokens and users")
    counters = _counters(obj["counters"])
    users_raw = _entries(obj["users"], USER_KEYS)
    tokens_raw = _entries(obj["tokens"], TOKEN_KEYS)
    dossiers_raw = _entries(obj["dossiers"], None)
    idempotency_raw = _entries(obj["idempotency"], None)

    state = State()
    state.counters = counters
    for entry in users_raw:
        user_id = _text(entry, "id")
        email = _text(entry, "email")
        display_name = _text(entry, "display_name")
        password_hash = _text(entry, "password_hash")
        if not is_valid_user_id(user_id) or not is_valid_encoding(password_hash):
            raise validation("state holds an invalid user")
        if user_id in state.users or email.lower() in state.emails:
            raise validation("state holds a duplicate user")
        state.add_user(user_id, email, display_name, password_hash, reserve=False)
    for entry in tokens_raw:
        token = _text(entry, "token")
        user_id = _text(entry, "user_id")
        if not token or user_id not in state.users or token in state.tokens:
            raise validation("state holds an invalid token")
        state.tokens[token] = user_id
    for entry in dossiers_raw:
        record = dossier_from_json(entry)
        if record["domain"] in state.dossiers or record["dossier_id"] in state.dossier_ids():
            raise validation("state holds a duplicate dossier")
        state.dossiers[record["domain"]] = record
    for entry in idempotency_raw:
        key, record = idempotency_from_json(entry, state.users)
        if key in state.idempotency:
            raise validation("state holds a duplicate idempotency record")
        state.idempotency[key] = record
    _check_issued(state)
    return state


def _counters(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or not set(value) <= set(COUNTER_PREFIXES):
        raise validation("state counters must be an object with user and dossier counts")
    counters: dict[str, int] = {}
    for name, number in value.items():
        if not isinstance(number, int) or isinstance(number, bool) or not 0 <= number <= MAX_COUNTER:
            raise validation("state counters must be integers from 0 to 10^12")
        counters[name] = number
    return counters


def _check_issued(state: State) -> None:
    """Every id the counters could have issued must be covered by its counter (RL17)."""
    for user_id in state.users:
        number = canonical_number("user", user_id)
        if number is not None and number > state.counters.get("user", 0):
            raise validation("state user counter is below an issued id")
    for dossier_id in state.dossier_ids():
        number = canonical_number("dossier", dossier_id)
        if number is not None and number > state.counters.get("dossier", 0):
            raise validation("state dossier counter is below an issued id")


def _entries(value: Any, keys: frozenset | None) -> list[dict]:
    if not isinstance(value, list):
        raise validation("state sections must be lists")
    for entry in value:
        if not isinstance(entry, dict):
            raise validation("state entries must be objects")
        if keys is not None and set(entry) != keys:
            raise validation("state entries must have exactly the expected keys")
    return value


def _text(entry: dict, key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str):
        raise validation(f"state field {key} must be a string")
    return value
