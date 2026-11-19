"""API error type and constructors for the §5 error envelope."""


class ApiError(Exception):
    """An error answered with the §5 envelope: HTTP status, code and message."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def malformed(message: str = "malformed request") -> ApiError:
    return ApiError(400, "malformed_request", message)


def missing_idempotency_key(message: str = "Idempotency-Key header is required") -> ApiError:
    return ApiError(400, "missing_idempotency_key", message)


def unauthenticated(message: str = "authentication required") -> ApiError:
    return ApiError(401, "unauthenticated", message)


def not_found(message: str = "not found") -> ApiError:
    return ApiError(404, "not_found", message)


def method_not_allowed(message: str = "method not allowed") -> ApiError:
    return ApiError(405, "method_not_allowed", message)


def email_taken(message: str = "email is already registered") -> ApiError:
    return ApiError(409, "email_taken", message)


def idempotency_key_reuse(message: str = "Idempotency-Key was used with a different request") -> ApiError:
    return ApiError(409, "idempotency_key_reuse", message)


def validation(message: str) -> ApiError:
    return ApiError(422, "validation_failed", message)
