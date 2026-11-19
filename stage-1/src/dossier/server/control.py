"""The test control endpoints: reset with a fixture, and the clock (spec 3.3, 3.4)."""

from datetime import datetime

from dossier.server.errors import malformed, validation
from dossier.server.fields import read_fields
from dossier.server.passwords import hash_password
from dossier.server.store import Store, User
from dossier.server.timestamps import parse_rfc3339

_USER_FIELDS = {"id": str, "email": str, "password": str, "display_name": str}


def parse_reset(body: dict) -> tuple[datetime, list[User]]:
    """Validate a fixture and build its users. Raises before any state changes."""
    fields = read_fields(body, {"now": str})
    instant = _parse_instant(fields["now"])
    raw_users = body.get("users", [])
    if not isinstance(raw_users, list):
        raise malformed("field users must be an array")
    entries = [_read_user_entry(entry) for entry in raw_users]
    _check_unique(entries)
    users = [
        User(entry["id"], entry["email"], entry["display_name"], hash_password(entry["password"]))
        for entry in entries
    ]
    return instant, users


def set_clock(store: Store, body: dict) -> None:
    fields = read_fields(body, {"now": str})
    instant = _parse_instant(fields["now"])
    with store.lock:
        if instant < store.clock.now():
            raise validation("now is earlier than the clock's current time")
        store.clock.set(instant)


def _parse_instant(text: str) -> datetime:
    instant = parse_rfc3339(text)
    if instant is None:
        raise validation("now must be an RFC 3339 timestamp with an explicit offset")
    return instant


def _read_user_entry(entry: object) -> dict:
    if not isinstance(entry, dict):
        raise malformed("each user must be a JSON object")
    fields = read_fields(entry, _USER_FIELDS)
    if not 1 <= len(fields["id"]) <= 64:
        raise validation("user id must be 1 to 64 characters")
    return fields


def _check_unique(entries: list[dict]) -> None:
    ids = [entry["id"] for entry in entries]
    emails = [entry["email"].casefold() for entry in entries]
    if len(set(ids)) != len(ids) or len(set(emails)) != len(emails):
        raise validation("fixture users must have distinct ids and emails")
