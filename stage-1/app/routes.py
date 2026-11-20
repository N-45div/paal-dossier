"""Route table and dispatch.

Order of checks for every request: route (404 unknown path, 405 wrong method), then bearer
authentication for authenticated routes, then the handler. Handlers do their own body and
field checks, so they run after authentication, as spec §6 requires.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from . import auth, control, dossier_api, health
from .context import App
from .errors import method_not_allowed, not_found
from .messages import Reply, Request

Handler = Callable[[App, Request], Reply]


@dataclass(frozen=True)
class Route:
    method: str
    pattern: re.Pattern[str]
    handler: Handler
    authenticated: bool


def route(
    method: str, template: str, handler: Handler, *, authenticated: bool = False
) -> Route:
    """Build a route; `{name}` in the template matches one path segment into `request.params`."""
    regex = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template)
    return Route(method, re.compile(regex), handler, authenticated)


ROUTES: tuple[Route, ...] = (
    route("GET", "/health", health.health),
    route("POST", "/_test/reset", control.reset),
    route("POST", "/_test/clock", control.move_clock),
    route("POST", "/auth/signup", auth.signup),
    route("POST", "/auth/login", auth.login),
    route("GET", "/_test/export", control.export_state),
    route("POST", "/_test/import", control.import_state),
    route("POST", "/dossiers", dossier_api.create_dossier, authenticated=True),
    route("GET", "/dossiers", dossier_api.list_dossiers, authenticated=True),
    route("GET", "/dossiers/{domain}", dossier_api.get_dossier, authenticated=True),
    route(
        "POST",
        "/dossiers/{domain}/refresh",
        dossier_api.refresh_dossier,
        authenticated=True,
    ),
)


class Router:
    def __init__(self, routes: tuple[Route, ...] = ROUTES) -> None:
        self._routes = routes

    def dispatch(self, app: App, request: Request) -> Reply:
        matches = [
            (candidate, match)
            for candidate in self._routes
            if (match := candidate.pattern.fullmatch(request.path)) is not None
        ]
        if not matches:
            raise not_found()
        for candidate, match in matches:
            if candidate.method != request.method:
                continue
            request.params = match.groupdict()
            if candidate.authenticated:
                request.user = auth.authenticate(
                    app.store, request.headers.get("Authorization")
                )
            return candidate.handler(app, request)
        raise method_not_allowed()
