"""API error type and the one JSON error body shape of the specification (§5)."""


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str = ""):
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message or code


def malformed(message: str = "malformed request") -> ApiError:
    return ApiError(400, "malformed_request", message)


def invalid(message: str = "validation failed") -> ApiError:
    return ApiError(422, "validation_failed", message)


def unauthenticated() -> ApiError:
    return ApiError(401, "unauthenticated", "missing or invalid bearer token")


def not_found(message: str = "not found") -> ApiError:
    return ApiError(404, "not_found", message)
