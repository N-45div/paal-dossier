"""Unauthenticated test-control endpoints: reset with fixture seeding, and the clock (§3.3, §3.4)."""

from __future__ import annotations

import re
from typing import Any

from aiohttp import web

from app.clock import parse_rfc3339
from app.errors import malformed, validation_failed
from app.passwords import hash_password
from app.state import STORE, State, Store, User
from app.validation import read_json_object, required_string, string_length_ok

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+$")


async def reset(request: web.Request) -> web.Response:
    store: Store = request.app[STORE]
    body = await read_json_object(request)
    now = parse_rfc3339(required_string(body, "now"))
    seeds = _parse_users(body.get("users", []))

    # Hash every seeded password before touching state, so a failed fixture changes nothing.
    new_state = State()
    for seed in seeds:
        user = User(
            id=seed["id"],
            email=seed["email"].lower(),
            display_name=seed["display_name"],
            password_hash=await hash_password(seed["password"]),
        )
        new_state.users_by_id[user.id] = user
        new_state.users_by_email[user.email] = user

    store.replace(new_state)
    store.clock.reset_to(now)
    return web.Response(status=204)


def _parse_users(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise malformed("users must be a list")
    seeds: list[dict[str, str]] = []
    ids: set[str] = set()
    emails: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise malformed("each user must be a JSON object")
        seed = {key: required_string(entry, key)
                for key in ("id", "email", "password", "display_name")}
        string_length_ok(seed["id"], 1, 64, "id")
        if not _EMAIL.match(seed["email"]):
            raise validation_failed("user email must be of the form local@domain")
        if not seed["password"]:
            raise validation_failed("user password must not be empty")
        string_length_ok(seed["display_name"], 1, 100, "display_name")
        email = seed["email"].lower()
        if seed["id"] in ids or email in emails:
            raise validation_failed("fixture users must have unique ids and emails")
        ids.add(seed["id"])
        emails.add(email)
        seeds.append(seed)
    return seeds


async def set_clock(request: web.Request) -> web.Response:
    store: Store = request.app[STORE]
    body = await read_json_object(request)
    store.clock.set(parse_rfc3339(required_string(body, "now")))
    return web.Response(status=204)
