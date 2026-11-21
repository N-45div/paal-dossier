"""HTTP application: error envelope middleware, routes, and the process entry point."""

from __future__ import annotations

import logging
import os

from aiohttp import web

from app import auth, control
from app.clock import Clock
from app.errors import ApiError, error_response, json_response
from app.state import STORE, Store

DEFAULT_PORT = 8080
log = logging.getLogger("dossier")


@web.middleware
async def error_envelope(request: web.Request, handler):
    """Render every failure as the §5 envelope. No response is ever a 5xx from a known path."""
    try:
        return await handler(request)
    except ApiError as err:
        return error_response(err.status, err.code, err.message)
    except web.HTTPException as err:
        if err.status == 404 or err.status == 405:
            return error_response(404, "not_found", "no such endpoint")
        return error_response(400, "malformed_request", err.reason or "malformed request")
    except Exception:  # a bug, not a spec case: log it and keep the envelope
        log.exception("unhandled error on %s %s", request.method, request.path)
        return error_response(500, "internal_error", "internal error")


async def health(request: web.Request) -> web.Response:
    return json_response({"status": "ok"})


def build_app(clock: Clock | None = None) -> web.Application:
    app = web.Application(middlewares=[error_envelope])
    app[STORE] = Store(clock or Clock())

    async def signup(request: web.Request) -> web.Response:
        return await auth.signup(request, request.app[STORE])

    async def login(request: web.Request) -> web.Response:
        return await auth.login(request, request.app[STORE])

    app.router.add_get("/health", health)
    app.router.add_post("/auth/signup", signup)
    app.router.add_post("/auth/login", login)
    app.router.add_post("/_test/reset", control.reset)
    app.router.add_post("/_test/clock", control.set_clock)
    return app


def port_from_env() -> int:
    raw = os.environ.get("PORT", "").strip()
    try:
        return int(raw) if raw else DEFAULT_PORT
    except ValueError:
        return DEFAULT_PORT


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    web.run_app(
        build_app(),
        host="0.0.0.0",
        port=port_from_env(),
        access_log=None,
        print=None,
    )
