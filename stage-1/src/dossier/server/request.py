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
    generation: int | None = None  # store generation at authentication; None when unauthenticated


def require_current(store, request: Request) -> None:
    """Caller holds store.lock. A request whose session predates a reset or import is refused:
    it is treated as made against the old state, which the new state no longer has (RL1.8)."""
    from dossier.server.errors import unauthenticated

    if request.generation is not None and request.generation != store.generation:
        raise unauthenticated("the session ended while the request was running")
