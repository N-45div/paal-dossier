"""Signup, login and bearer authentication (§6)."""
from __future__ import annotations

import asyncio
import secrets
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

from .errors import ApiError, invalid, malformed, unauthenticated
from .http import json_response, parse_json
from .passwords import hash_password, verify_password
from .state import Store, User


def authenticate(request: Request, store: Store) -> str:
    """Return the user id for the request's bearer token or raise 401."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token or token != token.strip():
        raise unauthenticated()
    user_id = store.tokens.get(token)
    if user_id is None:
        raise unauthenticated()
    return user_id


def object_body(raw: bytes) -> dict[str, Any]:
    try:
        body = parse_json(raw)
    except ValueError as exc:
        raise malformed("body is not valid JSON") from exc
    if not isinstance(body, dict):
        raise malformed("body must be a JSON object")
    return body


def _require_strings(body: dict[str, Any], names: tuple[str, ...]) -> dict[str, str]:
    for name in names:
        if name in body and not isinstance(body[name], str):
            raise malformed(f"{name} must be a string")
    missing = [name for name in names if name not in body]
    if missing:
        raise invalid(f"missing {', '.join(missing)}")
    return {name: body[name] for name in names}


def valid_email(email: str) -> bool:
    local, sep, domain = email.partition("@")
    return bool(sep) and "@" not in domain and bool(local) and bool(domain) and not any(c.isspace() for c in email)


def _session(store: Store, user: User) -> Response:
    return json_response({"user_id": user.user_id, "display_name": user.display_name, "token": store.issue_token(user.user_id)})


class AuthHandlers:
    def __init__(self, service: Any) -> None:
        self.service = service

    async def signup(self, request: Request) -> Response:
        body = object_body(await request.body())
        values = _require_strings(body, ("email", "password", "display_name"))
        if not valid_email(values["email"]):
            raise invalid("email must look like local@domain")
        if len(values["password"]) < 8:
            raise invalid("password must be at least 8 characters")
        name = values["display_name"]
        if not name.strip() or len(name) > 100:
            raise invalid("display_name must be 1 to 100 characters")
        if values["email"].lower() in self.service.store.user_by_email:
            raise ApiError(409, "email_taken", "email already registered")
        password_hash = await asyncio.to_thread(hash_password, values["password"])
        store = self.service.store
        if values["email"].lower() in store.user_by_email:
            raise ApiError(409, "email_taken", "email already registered")
        user = User("u_" + secrets.token_hex(8), values["email"], name, password_hash)
        store.add_user(user)
        response = _session(store, user)
        response.status_code = 201
        return response

    async def login(self, request: Request) -> Response:
        body = object_body(await request.body())
        values = _require_strings(body, ("email", "password"))
        store = self.service.store
        user_id = store.user_by_email.get(values["email"].lower())
        user = store.users.get(user_id) if user_id else None
        if user is None or not await asyncio.to_thread(verify_password, values["password"], user.password_hash):
            raise unauthenticated("wrong email or password")
        store = self.service.store
        if store.users.get(user.user_id) is not user:  # state was replaced while hashing
            raise unauthenticated("wrong email or password")
        return _session(store, user)
