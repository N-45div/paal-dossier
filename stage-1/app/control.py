"""Unauthenticated control endpoints: reset, clock, export, import (§3.3, §3.4, §10)."""
from __future__ import annotations

import asyncio
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

from .auth import object_body
from .clock import parse_rfc3339
from .errors import invalid, malformed
from .http import json_response, no_content, parse_json
from .passwords import hash_password
from .service import Service
from .snapshot import InvalidSnapshot, export_envelope, import_envelope
from .state import Store, User


def _moment(value: Any):
    if not isinstance(value, str):
        raise malformed("now must be a string")
    try:
        return parse_rfc3339(value)
    except ValueError as exc:
        raise invalid("now must be an RFC 3339 timestamp with an offset") from exc


def _fixture_users(raw: Any) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise malformed("users must be a list")
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            raise malformed("each user must be an object")
        for name in ("id", "email", "password", "display_name"):
            if name in item and not isinstance(item[name], str):
                raise malformed(f"user {name} must be a string")
        missing = [n for n in ("id", "email", "password", "display_name") if n not in item]
        if missing:
            raise invalid(f"user is missing {', '.join(missing)}")
        entries.append(item)
    emails = [u["email"].lower() for u in entries]
    ids = [u["id"] for u in entries]
    if len(set(emails)) != len(emails) or len(set(ids)) != len(ids):
        raise invalid("fixture users must have distinct emails and ids")
    return entries


class ControlHandlers:
    def __init__(self, service: Service) -> None:
        self.service = service

    async def reset(self, request: Request) -> Response:
        fixture = object_body(await request.body())
        if "now" not in fixture:
            raise invalid("now is required")
        moment = _moment(fixture["now"])
        entries = _fixture_users(fixture.get("users"))
        hashes = await asyncio.gather(*(asyncio.to_thread(hash_password, u["password"]) for u in entries))
        store = Store()
        for entry, password_hash in zip(entries, hashes):
            store.add_user(User(entry["id"], entry["email"], entry["display_name"], password_hash))
        self.service.replace_store(store)
        self.service.clock.set(moment)
        return no_content()

    async def set_clock(self, request: Request) -> Response:
        body = object_body(await request.body())
        if "now" not in body:
            raise invalid("now is required")
        moment = _moment(body["now"])
        if moment < self.service.clock.now():
            raise invalid("now is earlier than the current clock time")
        self.service.clock.set(moment)
        return no_content()

    async def export(self, request: Request) -> Response:
        return json_response(export_envelope(self.service.store))

    async def import_state(self, request: Request) -> Response:
        raw = await request.body()
        try:
            envelope = parse_json(raw)
        except ValueError as exc:
            raise malformed("body is not valid JSON") from exc
        try:
            store = import_envelope(envelope)
        except InvalidSnapshot as exc:
            raise invalid(str(exc)) from exc
        self.service.replace_store(store)
        return no_content()
