"""The application: routes, dispatch and the error envelope. Independent of sockets."""

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from . import auth_routes, control_routes, dossier_routes
from .builds import BuildRunner
from .clock import Clock
from .engine_adapter import run_build
from .errors import ApiError, unauthenticated
from .router import Router
from .store import Store, authenticate_in
from .wire import encode_json

log = logging.getLogger("dossier")

_BEARER = re.compile(r"^Bearer\s+(\S+)$", re.IGNORECASE)


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]  # lowercased header names
    body: bytes
    params: dict[str, str]
    user_id: str | None = None


@dataclass(frozen=True)
class Reply:
    status: int
    body: bytes | None  # None: no body (204)


class App:
    def __init__(self, clock: Clock | None = None, engine=None) -> None:
        self.clock = clock or Clock()
        self.store = Store(self.clock)
        self.runner = BuildRunner(self.store, engine or run_build)
        self.router = Router()
        control_routes.register(self.router)
        auth_routes.register(self.router)
        dossier_routes.register(self.router)

    def handle(self, method: str, target: str, headers: dict[str, str], body: bytes) -> Reply:
        try:
            return self._dispatch(method, target, headers, body)
        except ApiError as error:
            return _error_reply(error.status, error.code, error.message)
        except Exception:  # last resort; a bug if it ever shows
            log.exception("unhandled error")
            return _error_reply(500, "internal_error", "internal error")

    def _dispatch(self, method: str, target: str, headers: dict[str, str], body: bytes) -> Reply:
        parts = urlsplit(target)
        path = parts.path or "/"
        route, raw_params = self.router.match(method, path)
        params = {name: unquote(value) for name, value in raw_params.items()}
        request = Request(
            method=method,
            path=path,
            query=parse_qs(parts.query, keep_blank_values=True),
            headers=headers,
            body=body,
            params=params,
        )
        # Protected routes: authentication and the handler run under one hold of the state lock
        # (RL9, reset race), so a token a reset removed is refused by the state the handler sees.
        if route.public:
            status, payload = route.handler(self, request)  # signup and login hash outside the lock
        else:
            with self.store.transact() as (state, _generation):
                request.user_id = authenticate_in(state, _bearer_token(headers))
                status, payload = route.handler(self, request)
        if payload is None:
            return Reply(status, None)
        return Reply(status, encode_json(payload))


def _bearer_token(headers: dict[str, str]) -> str | None:
    value = headers.get("authorization")
    if value is None:
        return None
    match = _BEARER.match(value.strip())
    if match is None:
        raise unauthenticated("Authorization must be a bearer token")
    return match.group(1)


def _error_reply(status: int, code: str, message: str) -> Reply:
    envelope: dict[str, Any] = {"error": {"code": code, "message": message}}
    return Reply(status, encode_json(envelope))
