"""Export and import of the whole state as one versioned document (spec 10, RL1.8).

Export is a deep snapshot taken under the lock. A dossier with a build running is exported as
it was before that build began. Import validates everything before it replaces state.
"""

import copy
from dataclasses import dataclass
from datetime import datetime

from dossier.server.domains import require_domain
from dossier.server.errors import validation
from dossier.server.fields import parse_object
from dossier.server.model import FIELD_NAMES, Claim, Dossier, FieldValue, clean_citations, valid_value
from dossier.server.passwords import is_valid_hash
from dossier.server.request import Request
from dossier.server.service import Service
from dossier.server.store import Store, User
from dossier.server.timestamps import format_timestamp, parse_rfc3339

TRACK = "dossier"
FORMAT_VERSION = 1


@dataclass
class Loaded:
    users: list[User]
    tokens: dict[str, str]
    dossiers: list[Dossier]
    claims: dict[tuple[str, str, str, str], Claim]


def export_document(store: Store) -> dict:
    with store.lock:
        users = [
            {"id": u.user_id, "email": u.email, "display_name": u.display_name, "password_hash": u.password_hash}
            for u in store.users.values()
        ]
        tokens = [{"token": token, "user_id": user_id} for token, user_id in store.tokens.items()]
        dossiers = [_dossier_out(d) for d in store.dossiers.values()]
        claims = [
            {"user_id": k[0], "key": k[1], "method": k[2], "path": k[3], "body": c.body, "payload": copy.deepcopy(c.payload)}
            for k, c in store.claims.items()
            if c.done
        ]
    state = {"users": users, "tokens": tokens, "dossiers": dossiers, "claims": claims}
    return {"track": TRACK, "format_version": FORMAT_VERSION, "state": state}


def export_handler(service: Service, request: Request) -> tuple[int, dict]:
    return 200, export_document(service.store)


def import_handler(service: Service, request: Request) -> tuple[int, None]:
    loaded = load_document(parse_object(request.body))
    service.store.replace_state(
        users=loaded.users, tokens=loaded.tokens, dossiers=loaded.dossiers, claims=loaded.claims
    )
    return 204, None


def load_document(document: dict) -> Loaded:
    """Validate a whole export. Any problem raises 422 and nothing has been changed."""
    if document.get("track") != TRACK:
        raise validation("track must be dossier")
    version = document.get("format_version")
    if type(version) is not int or version != FORMAT_VERSION:
        raise validation("unsupported format_version")
    state = document.get("state")
    if not isinstance(state, dict):
        raise validation("state must be an object")
    users = _users(_list(state, "users"))
    user_ids = {user.user_id for user in users}
    return Loaded(
        users=users,
        tokens=_tokens(_list(state, "tokens"), user_ids),
        dossiers=_dossiers(_list(state, "dossiers")),
        claims=_claims(_list(state, "claims"), user_ids),
    )


def _dossier_out(dossier: Dossier) -> dict:
    return {
        "dossier_id": dossier.dossier_id,
        "domain": dossier.domain,
        "state": dossier.state,
        "researched_at": format_timestamp(dossier.researched_at) if dossier.researched_at else None,
        "spent_units": dossier.spent_units,
        "fields": {
            name: {"value": dossier.fields[name].value, "citations": copy.deepcopy(dossier.fields[name].citations)}
            for name in FIELD_NAMES
        },
    }


def _list(state: dict, key: str) -> list:
    value = state.get(key)
    if not isinstance(value, list):
        raise validation(f"state.{key} must be an array")
    return value


def _entry(item: object) -> dict:
    if not isinstance(item, dict):
        raise validation("each entry must be an object")
    return item


def _text(entry: dict, key: str, low: int, high: int) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not low <= len(value) <= high:
        raise validation(f"{key} must be a string of {low} to {high} characters")
    return value


def _users(items: list) -> list[User]:
    users, ids, emails = [], set(), set()
    for item in items:
        entry = _entry(item)
        user = User(
            user_id=_text(entry, "id", 1, 64),
            email=_text(entry, "email", 1, 320),
            display_name=_text(entry, "display_name", 0, 100),
            password_hash=entry.get("password_hash"),
        )
        if not is_valid_hash(user.password_hash) or user.user_id in ids or user.email.casefold() in emails:
            raise validation("invalid or duplicate user")
        ids.add(user.user_id)
        emails.add(user.email.casefold())
        users.append(user)
    return users


def _tokens(items: list, user_ids: set[str]) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for item in items:
        entry = _entry(item)
        token = _text(entry, "token", 1, 512)
        user_id = _text(entry, "user_id", 1, 64)
        if user_id not in user_ids or token in tokens:
            raise validation("invalid or duplicate token")
        tokens[token] = user_id
    return tokens


def _dossiers(items: list) -> list[Dossier]:
    dossiers, ids, domains = [], set(), set()
    for item in items:
        dossier = _dossier(_entry(item))
        if dossier.dossier_id in ids or dossier.domain in domains:
            raise validation("duplicate dossier")
        ids.add(dossier.dossier_id)
        domains.add(dossier.domain)
        dossiers.append(dossier)
    return dossiers


def _dossier(entry: dict) -> Dossier:
    domain = require_domain(_text(entry, "domain", 1, 253))
    if domain != entry["domain"]:
        raise validation("dossier domain must be normalised")
    state = entry.get("state")
    if state not in ("ready", "failed"):
        raise validation("dossier state must be ready or failed")
    spent = entry.get("spent_units")
    if type(spent) is not int or spent < 0:
        raise validation("spent_units must be a non-negative integer")
    return Dossier(
        dossier_id=_text(entry, "dossier_id", 1, 64),
        domain=domain,
        state=state,
        fields=_fields(entry.get("fields")),
        researched_at=_instant(entry.get("researched_at")),
        spent_units=spent,
    )


def _instant(text: object) -> datetime | None:
    if text is None:
        return None
    if not isinstance(text, str) or parse_rfc3339(text) is None:
        raise validation("researched_at must be null or an RFC 3339 timestamp")
    return parse_rfc3339(text)


def _fields(raw: object) -> dict[str, FieldValue]:
    if not isinstance(raw, dict) or set(raw) != set(FIELD_NAMES):
        raise validation("fields must hold exactly the six field names")
    fields = {}
    for name in FIELD_NAMES:
        entry = _entry(raw[name])
        value, citations = entry.get("value"), entry.get("citations")
        cleaned = clean_citations(citations)
        if cleaned is None or not valid_value(name, value):
            raise validation(f"field {name} is malformed")
        if (value is None) != (not cleaned):
            raise validation(f"field {name} must cite exactly when it is known")
        fields[name] = FieldValue(value, cleaned)
    return fields


def _claims(items: list, user_ids: set[str]) -> dict[tuple[str, str, str, str], Claim]:
    claims: dict[tuple[str, str, str, str], Claim] = {}
    for item in items:
        entry = _entry(item)
        user_id = entry.get("user_id")
        payload = entry.get("payload")
        if user_id not in user_ids or not isinstance(payload, dict):
            raise validation("invalid claim")
        key = (
            user_id,
            _text(entry, "key", 1, 255),
            _text(entry, "method", 1, 16),
            _text(entry, "path", 1, 2048),
        )
        if key in claims or not isinstance(entry.get("body"), str):
            raise validation("duplicate or malformed claim")
        claims[key] = Claim(body=entry["body"], done=True, payload=payload)
    return claims
