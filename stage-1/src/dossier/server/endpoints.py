"""Endpoint handlers for the platform routes. Each returns (status, payload)."""

from dossier.server import accounts, control
from dossier.server.fields import parse_object
from dossier.server.store import Store


def health(store: Store, body: bytes, user_id: str | None) -> tuple[int, dict]:
    return 200, {"status": "ok"}


def signup(store: Store, body: bytes, user_id: str | None) -> tuple[int, dict]:
    return 201, _session_payload(accounts.signup(store, parse_object(body)))


def login(store: Store, body: bytes, user_id: str | None) -> tuple[int, dict]:
    return 200, _session_payload(accounts.login(store, parse_object(body)))


def reset(store: Store, body: bytes, user_id: str | None) -> tuple[int, None]:
    instant, users = control.parse_reset(parse_object(body))
    store.reset(instant, users)
    return 204, None


def set_clock(store: Store, body: bytes, user_id: str | None) -> tuple[int, None]:
    control.set_clock(store, parse_object(body))
    return 204, None


def _session_payload(session: accounts.Session) -> dict:
    return {"user_id": session.user_id, "display_name": session.display_name, "token": session.token}
