"""HTTP application: error envelope middleware, routes, and the process entry point."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from aiohttp import web

from app import auth, changes, control, dossiers, snapshot, values_api
from app.clock import Clock
from app.persist import Persister, load as load_state
from app.errors import ApiError, error_response, json_response
from app.state import STORE, Store
from app.ui import routes as ui_routes

DEFAULT_PORT = 8080
DEFAULT_DATA_DIR = "/srv/dossier/data"
STATE_FILE = "state.json"
log = logging.getLogger("dossier")


@web.middleware
async def persist_writes(request: web.Request, handler):
    """Every write is durable before its response is sent (Rul-S3-2)."""
    response = await handler(request)
    if request.method not in ("GET", "HEAD"):
        request.app[STORE].save()
    return response


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


def build_app(clock: Clock | None = None, data_dir: Path | None = None) -> web.Application:
    """The application. With `data_dir`, state is durable there and an existing state document is
    loaded first; without it, state lives in memory only (tests)."""
    app = web.Application(middlewares=[error_envelope, persist_writes])
    store = Store(clock or Clock(), Persister(data_dir / STATE_FILE) if data_dir else None)
    if store.persister is not None and store.persister.exists():
        state, fixed = load_state(store.persister.read())
        store.state = state
        if fixed is not None:
            store.clock.reset_to(fixed)
    app[STORE] = store

    async def signup(request: web.Request) -> web.Response:
        return await auth.signup(request, request.app[STORE])

    async def login(request: web.Request) -> web.Response:
        return await auth.login(request, request.app[STORE])

    app.router.add_get("/health", health)
    app.router.add_post("/auth/signup", signup)
    app.router.add_post("/auth/login", login)
    app.router.add_post("/_test/reset", control.reset)
    app.router.add_post("/_test/clock", control.set_clock)
    app.router.add_get("/_test/export", snapshot.export)
    app.router.add_post("/_test/import", snapshot.import_)
    app.router.add_post("/dossiers", dossiers.create)
    app.router.add_get("/dossiers", dossiers.list_all)
    app.router.add_get("/dossiers/{domain}", dossiers.get_one)
    app.router.add_post("/dossiers/{domain}/refresh", dossiers.refresh)
    app.router.add_get("/dossiers/{domain}/history", changes.history)
    app.router.add_get("/dossiers/{domain}/values", values_api.values)
    app.router.add_get("/changes", changes.changes)
    ui_routes.register(app)
    return app


def port_from_env() -> int:
    raw = os.environ.get("PORT", "").strip()
    try:
        return int(raw) if raw else DEFAULT_PORT
    except ValueError:
        return DEFAULT_PORT


def data_dir_from_env() -> Path:
    return Path(os.environ.get("DOSSIER_DATA_DIR", "").strip() or DEFAULT_DATA_DIR)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    web.run_app(
        build_app(data_dir=data_dir_from_env()),
        host="0.0.0.0",
        port=port_from_env(),
        access_log=None,
        print=None,
    )
