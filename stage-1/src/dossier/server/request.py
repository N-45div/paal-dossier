"""One parsed HTTP request, as the handlers see it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    method: str
    path: str  # the raw path as sent, without the query string
    query: dict[str, str]  # first value of each query parameter
    params: dict[str, str]  # path parameters, still percent-encoded
    body: bytes
    user_id: str | None
    idempotency_key: str | None
