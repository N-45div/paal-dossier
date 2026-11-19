"""ASGI application wiring."""
from __future__ import annotations

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from .auth import AuthHandlers
from .control import ControlHandlers
from .dossiers import DossierHandlers
from .errors import ApiError, handle_api_error, handle_http_exception, handle_unexpected
from .http import json_response
from .research_adapter import RunBuild, run_build
from .service import Service


async def health(_: Request) -> Response:
    return json_response({"status": "ok"})


def create_app(engine: RunBuild = run_build) -> Starlette:
    service = Service(engine)
    auth = AuthHandlers(service)
    control = ControlHandlers(service)
    dossiers = DossierHandlers(service)
    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/_test/reset", control.reset, methods=["POST"]),
        Route("/_test/clock", control.set_clock, methods=["POST"]),
        Route("/_test/export", control.export, methods=["GET"]),
        Route("/_test/import", control.import_state, methods=["POST"]),
        Route("/auth/signup", auth.signup, methods=["POST"]),
        Route("/auth/login", auth.login, methods=["POST"]),
        Route("/dossiers", dossiers.create, methods=["POST"]),
        Route("/dossiers", dossiers.listing, methods=["GET"]),
        Route("/dossiers/{domain:path}/refresh", dossiers.refresh, methods=["POST"]),
        Route("/dossiers/{domain:path}", dossiers.read, methods=["GET"]),
    ]
    return Starlette(
        routes=routes,
        exception_handlers={
            ApiError: handle_api_error,
            HTTPException: handle_http_exception,
            Exception: handle_unexpected,
        },
    )


app = create_app()
