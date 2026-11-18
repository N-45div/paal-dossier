"""ASGI application assembly and uniform error handling."""
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Route

from app.errors import ApiError
from app.http import error_response
from app.routes import auth, control, dossiers
from app.store import Store


async def _api_error(request: Request, exc: ApiError):
    return error_response(exc)


async def _http_error(request: Request, exc: HTTPException):
    headers = dict(exc.headers or {})
    return error_response(ApiError(exc.status_code, "not_found", "no such route or method"), headers)


async def _unexpected(request: Request, exc: Exception):
    return error_response(ApiError(500, "internal_error", "internal error"))


def create_app() -> Starlette:
    routes = [
        Route("/health", control.health, methods=["GET"]),
        Route("/_test/reset", control.reset, methods=["POST"]),
        Route("/_test/clock", control.set_clock, methods=["POST"]),
        Route("/_test/export", control.export_state, methods=["GET"]),
        Route("/_test/import", control.import_state, methods=["POST"]),
        Route("/dossiers", dossiers.create, methods=["POST"]),
        Route("/dossiers", dossiers.listing, methods=["GET"]),
        Route("/dossiers/{domain}", dossiers.read, methods=["GET"]),
        Route("/dossiers/{domain}/refresh", dossiers.refresh, methods=["POST"]),
        Route("/auth/signup", auth.signup, methods=["POST"]),
        Route("/auth/login", auth.login, methods=["POST"]),
    ]
    app = Starlette(routes=routes, exception_handlers={
        ApiError: _api_error, HTTPException: _http_error, Exception: _unexpected})
    app.router.redirect_slashes = False
    app.state.store = Store()
    return app


app = create_app()
