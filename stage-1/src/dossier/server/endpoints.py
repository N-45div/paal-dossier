"""Platform endpoints: health, signup and login, and the test controls (spec 3, 6)."""

from dossier.server import accounts, control
from dossier.server.fields import parse_object
from dossier.server.request import Request
from dossier.server.service import Service


def health(service: Service, request: Request) -> tuple[int, dict]:
    return 200, {"status": "ok"}


def signup(service: Service, request: Request) -> tuple[int, dict]:
    return 201, _session_payload(accounts.signup(service.store, parse_object(request.body)))


def login(service: Service, request: Request) -> tuple[int, dict]:
    return 200, _session_payload(accounts.login(service.store, parse_object(request.body)))


def reset(service: Service, request: Request) -> tuple[int, None]:
    instant, users = control.parse_reset(parse_object(request.body))
    service.store.replace_state(users=users, tokens={}, dossiers=[], claims={}, instant=instant)
    return 204, None


def set_clock(service: Service, request: Request) -> tuple[int, None]:
    control.set_clock(service.store, parse_object(request.body))
    return 204, None


def _session_payload(session: accounts.Session) -> dict:
    return {"user_id": session.user_id, "display_name": session.display_name, "token": session.token}
