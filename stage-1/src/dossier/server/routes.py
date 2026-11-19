"""The route table and dispatch: match, authenticate, then run the handler.

Authentication runs before any body validation (RL1.4), and an unknown route is 404.
"""

import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from dossier.server import accounts, dossiers, endpoints, snapshot
from dossier.server.errors import not_found
from dossier.server.query import parse_query
from dossier.server.request import Request
from dossier.server.service import Service

Handler = Callable[[Service, Request], tuple[int, "dict | None"]]


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
    _route("GET", r"/_test/export", snapshot.export_handler),
    _route("POST", r"/_test/import", snapshot.import_handler),
    _route("POST", r"/dossiers", dossiers.post_dossiers, needs_auth=True),
    _route("GET", r"/dossiers", dossiers.list_dossiers, needs_auth=True),
    _route("GET", r"/dossiers/(?P<domain>[^/]+)", dossiers.get_dossier, needs_auth=True),
    _route("POST", r"/dossiers/(?P<domain>[^/]+)/refresh", dossiers.post_refresh, needs_auth=True),
]


def dispatch(
    service: Service,
    method: str,
    target: str,
    authorization: str | None,
    idempotency_key: str | None,
    body: bytes,
) -> tuple[int, dict | None]:
    """Run the matching handler. Raises ApiError for every failure."""
    parts = urlsplit(target)
    for route in ROUTES:
        if route.method != method:
            continue
        match = route.pattern.fullmatch(parts.path)
        if match is None:
            continue
        user_id = accounts.authenticate(service.store, authorization) if route.needs_auth else None
        request = Request(
            method=method,
            path=parts.path,
            query=parse_query(parts.query),
            params=match.groupdict(),
            body=body,
            user_id=user_id,
            idempotency_key=idempotency_key,
        )
        return route.handler(service, request)
    raise not_found()
