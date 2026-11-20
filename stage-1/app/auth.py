"""Signup, login and bearer authentication (spec §6)."""

from __future__ import annotations

import re

from .context import App
from .errors import email_taken, unauthenticated
from .messages import Reply, Request, json_reply
from .passwords import hash_password, verify_password
from .store import Store, User
from .validation import (
    check_display_name,
    check_password,
    new_id,
    normalise_email,
    parse_object,
    required_string,
)

_BEARER = re.compile(r"Bearer\s+(\S+)", re.IGNORECASE)


def authenticate(store: Store, authorization: str | None) -> User:
    """Return the user a bearer token belongs to, or raise 401 unauthenticated."""
    if authorization is None:
        raise unauthenticated()
    match = _BEARER.fullmatch(authorization.strip())
    if match is None:
        raise unauthenticated()
    user = store.user_by_token(match.group(1))
    if user is None:
        raise unauthenticated()
    return user


def signup(app: App, request: Request) -> Reply:
    body = parse_object(request.body)
    email = normalise_email(required_string(body, "email"))
    password = required_string(body, "password")
    display_name = required_string(body, "display_name")
    check_password(password)
    check_display_name(display_name)
    password_hash = hash_password(password)
    with app.store.lock:
        if app.store.user_by_email(email) is not None:
            raise email_taken()
        user = User(
            id=new_id("u"), email=email, display_name=display_name, password_hash=password_hash
        )
        app.store.add_user(user)
        token = app.store.issue_token(user.id)
    return json_reply(201, _session_body(user, token))


def login(app: App, request: Request) -> Reply:
    body = parse_object(request.body)
    email = required_string(body, "email").lower()
    password = required_string(body, "password")
    user = app.store.user_by_email(email)
    if user is None or not verify_password(password, user.password_hash):
        raise unauthenticated("wrong email or password")
    with app.store.lock:
        # Verification ran outside the lock; a reset in between invalidates this user.
        if app.store.user_by_id(user.id) is not user:
            raise unauthenticated("wrong email or password")
        token = app.store.issue_token(user.id)
    return json_reply(200, _session_body(user, token))


def _session_body(user: User, token: str) -> dict[str, str]:
    return {"user_id": user.id, "display_name": user.display_name, "token": token}
