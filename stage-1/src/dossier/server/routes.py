"""The route table and dispatch: match, authenticate, then run the handler.

Authentication runs before any body validation (RL1.4), and an unknown route is 404.
"""

import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from dossier.server import accounts, endpoints
from dossier.server.errors import not_found
from dossier.server.store import Store

Handler = Callable[[Store, bytes, "str | None"], tuple[int, "dict | None"]]


@dataclass(frozen=True)
class Route:
    method: str
    pattern: "re.Pattern[str]"
    handler: Handler
    needs_auth: bool


def _route(method: str, pattern: str, handler: Handler, needs_auth: bool = False) -> Route:
    return Route(method, re.compile(pattern), handler, needs_auth)


ROUTES = [
    _route("GET", r"/health", endpoints.health),
    _route("POST", r"/auth/signup", endpoints.signup),
    _route("POST", r"/auth/login", endpoints.login),
    _route("POST", r"/_test/reset", endpoints.reset),
    _route("POST", r"/_test/clock", endpoints.set_clock),
]


def dispatch(store: Store, method: str, target: str, authorization: str | None, body: bytes) -> tuple[int, dict | None]:
    """Run the matching handler. Raises ApiError for every failure."""
    path = urlsplit(target).path
    for route in ROUTES:
        if route.method != method or route.pattern.fullmatch(path) is None:
            continue
        user_id = accounts.authenticate(store, authorization) if route.needs_auth else None
        return route.handler(store, body, user_id)
    raise not_found()
