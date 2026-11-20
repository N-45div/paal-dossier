"""The reset fixture (spec §3.3, §4), parsed completely before any state changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .clock import parse_rfc3339
from .errors import malformed, validation_failed
from .passwords import hash_password
from .store import User
from .validation import normalise_email, required_string

MAX_ID_LENGTH = 64


@dataclass(frozen=True)
class Fixture:
    now: datetime
    users: tuple[User, ...]


def parse_fixture(body: dict[str, Any]) -> Fixture:
    now = parse_rfc3339(required_string(body, "now"))
    raw_users = body.get("users")
    if raw_users is None:
        raw_users = []
    if not isinstance(raw_users, list):
        raise malformed("users must be a list")
    users: list[User] = []
    seen_ids: set[str] = set()
    seen_emails: set[str] = set()
    for item in raw_users:
        if not isinstance(item, dict):
            raise malformed("each user must be a JSON object")
        user_id = required_string(item, "id")
        if not 1 <= len(user_id) <= MAX_ID_LENGTH:
            raise validation_failed("user id must be 1 to 64 characters")
        email = normalise_email(required_string(item, "email"))
        password = required_string(item, "password")
        display_name = required_string(item, "display_name")
        if not password:
            raise validation_failed("password must not be empty")
        if user_id in seen_ids or email in seen_emails:
            raise validation_failed("fixture repeats a user id or an email")
        seen_ids.add(user_id)
        seen_emails.add(email)
        users.append(
            User(
                id=user_id,
                email=email,
                display_name=display_name,
                password_hash=hash_password(password),
            )
        )
    return Fixture(now=now, users=tuple(users))
