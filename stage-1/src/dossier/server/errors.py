"""The error envelope every 4xx and 5xx response carries (spec section 5)."""


class ApiError(Exception):
    """A request failed with a specified status and code."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def payload(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def malformed(message: str = "request body must be a JSON object") -> ApiError:
    return ApiError(400, "malformed_request", message)


def missing_idempotency_key() -> ApiError:
    return ApiError(400, "missing_idempotency_key", "Idempotency-Key header is required")


def validation(message: str) -> ApiError:
    return ApiError(422, "validation_failed", message)


def unauthenticated(message: str = "missing or invalid bearer token") -> ApiError:
    return ApiError(401, "unauthenticated", message)


def not_found(message: str = "no such resource") -> ApiError:
    return ApiError(404, "not_found", message)


def email_taken() -> ApiError:
    return ApiError(409, "email_taken", "email is already registered")


def idempotency_key_reuse() -> ApiError:
    return ApiError(
        409, "idempotency_key_reuse", "Idempotency-Key was already used with a different body"
    )
