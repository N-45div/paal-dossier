"""Error responses in the shape of spec §5."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """A request failed with a specified HTTP status and error code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def malformed(message: str = "malformed request") -> ApiError:
    return ApiError(400, "malformed_request", message)


def unauthenticated(message: str = "missing or invalid bearer token") -> ApiError:
    return ApiError(401, "unauthenticated", message)


def not_found(message: str = "no such resource") -> ApiError:
    return ApiError(404, "not_found", message)


def method_not_allowed(message: str = "method not allowed for this path") -> ApiError:
    return ApiError(405, "method_not_allowed", message)


def email_taken(message: str = "email is already registered") -> ApiError:
    return ApiError(409, "email_taken", message)


def missing_idempotency_key(message: str = "Idempotency-Key header is required") -> ApiError:
    return ApiError(400, "missing_idempotency_key", message)


def idempotency_key_reuse(
    message: str = "Idempotency-Key was already used with a different request body"
) -> ApiError:
    return ApiError(409, "idempotency_key_reuse", message)


def validation_failed(message: str = "validation failed") -> ApiError:
    return ApiError(422, "validation_failed", message)


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}
