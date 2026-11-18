"""Bearer-token authentication for protected endpoints (§6)."""
from starlette.requests import Request

from app.errors import unauthenticated
from app.store import State, User


def authenticate(request: Request, state: State) -> User:
    parts = request.headers.get("authorization", "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise unauthenticated()
    user_id = state.tokens.get(parts[1])
    user = state.users.get(user_id) if user_id else None
    if user is None:
        raise unauthenticated()
    return user
