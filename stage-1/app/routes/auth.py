"""Signup and login (§6)."""
from starlette.requests import Request

from app.errors import ApiError, invalid, unauthenticated
from app.fields import require
from app.http import json_object, json_response
from app.passwords import hash_password_async, verify_password_async
from app.store import Store, User, new_id


def _valid_email(email: str) -> bool:
    local, sep, domain = email.partition("@")
    return bool(sep and local and domain and "@" not in domain
                and not any(c.isspace() for c in email))


def _session(user: User, token: str, status: int):
    return json_response({"user_id": user.user_id, "display_name": user.display_name,
                          "token": token}, status)


async def signup(request: Request):
    store: Store = request.app.state.store
    email, password, display_name = require(await json_object(request),
                                            ("email", "password", "display_name"))
    if not _valid_email(email):
        raise invalid("email must look like local@domain")
    if len(password) < 8:
        raise invalid("password must be at least 8 characters")
    if not display_name.strip() or len(display_name) > 100:
        raise invalid("display_name must be 1 to 100 characters")
    password_hash = await hash_password_async(password)
    state = store.state
    if state.user_by_email(email):
        raise ApiError(409, "email_taken", "email is already registered")
    user = User(new_id("u"), email, display_name, password_hash)
    state.add_user(user)
    return _session(user, state.issue_token(user.user_id), 201)


async def login(request: Request):
    store: Store = request.app.state.store
    email, password = require(await json_object(request), ("email", "password"))
    user = store.state.user_by_email(email)
    if user is None or not await verify_password_async(password, user.password_hash):
        raise unauthenticated()
    return _session(user, store.state.issue_token(user.user_id), 200)
