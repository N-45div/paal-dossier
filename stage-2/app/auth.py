"""Signup, login and bearer-token authentication (spec §6)."""

from __future__ import annotations

import re
import secrets

from aiohttp import web

from app.errors import email_taken, json_response, unauthenticated, validation_failed
from app.passwords import hash_password, verify_password
from app.state import State, Store, User
from app.validation import read_json_object, required_string, string_length_ok

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+$")
_MIN_PASSWORD = 8
_MAX_DISPLAY_NAME = 100


def normalise_email(email: str) -> str:
    return email.lower()


def new_user_id() -> str:
    return "u_" + secrets.token_hex(8)


def new_token() -> str:
    return "tok_" + secrets.token_urlsafe(32)


def issue_token(state: State, user_id: str) -> str:
    token = new_token()
    state.tokens[token] = user_id
    return token


def authenticate(request: web.Request, store: Store) -> User:
    """Return the user for a valid `Authorization: Bearer <token>` header, else 401."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthenticated()
    state = store.state
    user_id = state.tokens.get(token.strip())
    if user_id is None:
        raise unauthenticated()
    return state.users_by_id[user_id]


async def signup(request: web.Request, store: Store) -> web.Response:
    body = await read_json_object(request)
    email = required_string(body, "email")
    password = required_string(body, "password")
    display_name = required_string(body, "display_name")
    if not _EMAIL.match(email):
        raise validation_failed("email must be of the form local@domain")
    if len(password) < _MIN_PASSWORD:
        raise validation_failed("password must be at least 8 characters")
    string_length_ok(display_name, 1, _MAX_DISPLAY_NAME, "display_name")

    key = normalise_email(email)
    if key in store.state.users_by_email:
        raise email_taken()
    password_hash = await hash_password(password)

    # Re-check after the await: another signup may have claimed the address meanwhile.
    state = store.state
    if key in state.users_by_email:
        raise email_taken()
    user = User(id=new_user_id(), email=key, display_name=display_name,
                password_hash=password_hash)
    state.users_by_id[user.id] = user
    state.users_by_email[key] = user
    token = issue_token(state, user.id)
    return json_response(
        {"user_id": user.id, "display_name": user.display_name, "token": token}, status=201
    )


async def login(request: web.Request, store: Store) -> web.Response:
    body = await read_json_object(request)
    email = required_string(body, "email")
    password = required_string(body, "password")
    user = store.state.users_by_email.get(normalise_email(email))
    if user is None or not await verify_password(password, user.password_hash):
        raise unauthenticated("wrong email or password")
    # The state may have been reset while hashing; the token belongs to the state now current.
    state = store.state
    current = state.users_by_id.get(user.id)
    if current is None or current is not user:
        raise unauthenticated("wrong email or password")
    token = issue_token(state, user.id)
    return json_response(
        {"user_id": user.id, "display_name": user.display_name, "token": token}
    )
