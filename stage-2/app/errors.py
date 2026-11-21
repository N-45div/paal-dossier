"""The error envelope of spec §5 and the exceptions that produce it."""

from __future__ import annotations

import json

from aiohttp import web


class ApiError(Exception):
    """An error with a spec status and code, rendered as the §5 envelope."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def malformed(message: str = "malformed request") -> ApiError:
    return ApiError(400, "malformed_request", message)


def missing_idempotency_key() -> ApiError:
    return ApiError(400, "missing_idempotency_key", "Idempotency-Key header is required")


def unauthenticated(message: str = "missing or invalid bearer token") -> ApiError:
    return ApiError(401, "unauthenticated", message)


def not_found(message: str = "not found") -> ApiError:
    return ApiError(404, "not_found", message)


def idempotency_key_reuse() -> ApiError:
    return ApiError(
        409, "idempotency_key_reuse", "Idempotency-Key was already used with a different body"
    )


def email_taken() -> ApiError:
    return ApiError(409, "email_taken", "email is already registered")


def validation_failed(message: str) -> ApiError:
    return ApiError(422, "validation_failed", message)


def error_response(status: int, code: str, message: str) -> web.Response:
    return json_response(
        {"error": {"code": code, "message": message}}, status=status
    )


def json_response(payload: object, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(payload, ensure_ascii=False),
        status=status,
        content_type="application/json",
        charset="utf-8",
    )
