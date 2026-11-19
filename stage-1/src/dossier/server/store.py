"""In-memory service state behind one lock (RL1.1, RL1.8).

Every read and write of state happens while holding `lock`. `generation` moves on every
reset and import, so a build that started earlier can tell its result is stale.
"""

import threading
from dataclasses import dataclass
from datetime import datetime

from dossier.server.clock import Clock


@dataclass(frozen=True)
class User:
    user_id: str
    email: str
    display_name: str
    password_hash: str


class Store:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.clock = Clock()
        self.generation = 0
        self.users: dict[str, User] = {}
        self.user_by_email: dict[str, str] = {}
        self.tokens: dict[str, str] = {}

    def reset(self, instant: datetime, users: list[User]) -> None:
        """Replace all state with a fixture. Caller has validated everything."""
        with self.lock:
            self.generation += 1
            self.clock.set(instant)
            self.users = {user.user_id: user for user in users}
            self.user_by_email = {user.email.casefold(): user.user_id for user in users}
            self.tokens = {}
