"""In-memory service state.

The service runs on one asyncio loop; every mutation below is a synchronous
section (no await inside), so each is atomic with respect to other requests.
"""
import asyncio
import secrets
from dataclasses import dataclass, field

from app.clock import Clock
from app.dossiers import Dossier
from app.idempotency import Record


@dataclass
class User:
    user_id: str
    email: str
    display_name: str
    password_hash: str


@dataclass
class State:
    clock: Clock = field(default_factory=Clock)
    users: dict[str, User] = field(default_factory=dict)
    email_index: dict[str, str] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)
    dossiers: dict[str, Dossier] = field(default_factory=dict)      # by normalised domain
    idempotency: dict[tuple, Record] = field(default_factory=dict)  # (user, method, path, key)

    def add_user(self, user: User) -> None:
        self.users[user.user_id] = user
        self.email_index[user.email.lower()] = user.user_id

    def user_by_email(self, email: str) -> User | None:
        user_id = self.email_index.get(email.lower())
        return self.users.get(user_id) if user_id else None

    def issue_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens[token] = user_id
        return token


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


class Store:
    """Holder of the current State; reset replaces it wholesale."""

    def __init__(self) -> None:
        self.state = State()
        self.generation = 0
        self.tasks: set[asyncio.Task] = set()

    def replace(self, state: State) -> None:
        self.state = state
        self.generation += 1
        for task in list(self.tasks):
            task.cancel()
