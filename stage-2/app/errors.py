"""API errors rendered with the §5 body."""
from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response
from starlette.exceptions import HTTPException

from .http import json_response


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message or code


def malformed(message: str = "malformed request") -> ApiError:
    return ApiError(400, "malformed_request", message)


def invalid(message: str = "validation failed") -> ApiError:
    return ApiError(422, "validation_failed", message)


def unauthenticated(message: str = "missing or invalid bearer token") -> ApiError:
    return ApiError(401, "unauthenticated", message)


def not_found(message: str = "not found") -> ApiError:
    return ApiError(404, "not_found", message)


def error_response(status: int, code: str, message: str) -> Response:
    return json_response({"error": {"code": code, "message": message}}, status)


async def handle_api_error(_: Request, exc: Exception) -> Response:
    assert isinstance(exc, ApiError)
    return error_response(exc.status, exc.code, exc.message)


async def handle_http_exception(_: Request, exc: Exception) -> Response:
    assert isinstance(exc, HTTPException)
    # Unknown paths and unsupported methods both use the not_found code (ruling L1.10).
    return error_response(exc.status_code, "not_found", "no such route")


async def handle_unexpected(_: Request, exc: Exception) -> Response:
    return error_response(500, "internal_error", "internal error")
