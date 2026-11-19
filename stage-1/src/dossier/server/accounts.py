"""Signup, login and bearer-token authentication (spec 6)."""

import re
import secrets
from dataclasses import dataclass

from dossier.server.errors import email_taken, unauthenticated, validation
from dossier.server.fields import read_fields
from dossier.server.passwords import hash_password, verify_password
from dossier.server.store import Store, User

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")
_BEARER = re.compile(r"Bearer ([^\s]+)", re.IGNORECASE)
_SIGNUP_FIELDS = {"email": str, "password": str, "display_name": str}
_LOGIN_FIELDS = {"email": str, "password": str}


@dataclass(frozen=True)
class Session:
    user_id: str
    display_name: str
    token: str


def new_token() -> str:
    return secrets.token_urlsafe(32)


def signup(store: Store, body: dict) -> Session:
    fields = read_fields(body, _SIGNUP_FIELDS)
    email, password, display_name = fields["email"], fields["password"], fields["display_name"]
    _check_email(email)
    _check_password(password)
    _check_display_name(display_name)
    with store.lock:
        if email.casefold() in store.user_by_email:
            raise email_taken()
        generation = store.generation
        user_id = _new_user_id(store)
    password_hash = hash_password(password)  # slow, outside the lock
    token = new_token()
    with store.lock:
        if store.generation != generation:
            # A reset or import landed while hashing: this signup belongs to the old state,
            # which that reset discarded. Nothing is stored, so neither the user nor the token
            # survives into the new state (R1.25, R1.143).
            return Session(user_id, display_name, token)
        if email.casefold() in store.user_by_email:
            raise email_taken()  # a concurrent signup took the address first
        store.users[user_id] = User(user_id, email, display_name, password_hash)
        store.user_by_email[email.casefold()] = user_id
        store.tokens[token] = user_id
    return Session(user_id, display_name, token)


def login(store: Store, body: dict) -> Session:
    """Check the password outside the lock, then issue a token only if no reset or import
    happened meanwhile: a login that raced a reset is refused, as if it came after it."""
    fields = read_fields(body, _LOGIN_FIELDS)
    with store.lock:
        user_id = store.user_by_email.get(fields["email"].casefold())
        user = store.users.get(user_id) if user_id else None
        generation = store.generation
    if user is None or not verify_password(fields["password"], user.password_hash):
        raise unauthenticated("wrong email or password")
    with store.lock:
        if store.generation != generation:
            raise unauthenticated("the account changed during login")
        token = _issue_token(store, user.user_id)
    return Session(user.user_id, user.display_name, token)


def authenticate(store: Store, authorization: str | None) -> tuple[str, int]:
    """Return (user id, state generation) for a valid bearer token, else 401.

    Both are read under one lock section, so the generation is the one the token was valid in.
    """
    match = _BEARER.fullmatch(authorization or "")
    if match is None:
        raise unauthenticated()
    with store.lock:
        user_id = store.tokens.get(match.group(1))
        generation = store.generation
    if user_id is None:
        raise unauthenticated()
    return user_id, generation


def _issue_token(store: Store, user_id: str) -> str:
    token = new_token()
    store.tokens[token] = user_id
    return token


def _new_user_id(store: Store) -> str:
    while True:
        user_id = "u_" + secrets.token_hex(8)
        if user_id not in store.users:
            return user_id


def _check_email(email: str) -> None:
    if not _EMAIL.fullmatch(email):
        raise validation("email must be of the form local@domain")


def _check_password(password: str) -> None:
    if len(password) < 8:
        raise validation("password must be at least 8 characters")


def _check_display_name(display_name: str) -> None:
    if display_name.strip() == "" or len(display_name) > 100:
        raise validation("display_name must be 1 to 100 characters")
