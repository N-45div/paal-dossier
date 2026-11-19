"""In-memory service state behind one lock (RL1.1, RL1.8).

Every read and write of state happens while holding `lock`, a Condition so that identical
concurrent requests can wait for the first one. `generation` moves on every reset and import:
a build started earlier then has its cancel event set and its result discarded.
"""

import threading
from dataclasses import dataclass
from datetime import datetime

from dossier.server.clock import Clock
from dossier.server.model import Build, Claim, Dossier


@dataclass(frozen=True)
class User:
    user_id: str
    email: str
    display_name: str
    password_hash: str


class Store:
    def __init__(self) -> None:
        self.lock = threading.Condition()
        self.clock = Clock()
        self.generation = 0
        self.users: dict[str, User] = {}
        self.user_by_email: dict[str, str] = {}
        self.tokens: dict[str, str] = {}
        self.dossiers: dict[str, Dossier] = {}  # by normalised domain
        self.claims: dict[tuple[str, str, str, str], Claim] = {}
        self.running: set[Build] = set()
        self.reservations: dict[str, object] = {}  # casefolded email -> signup in flight

    def replace_state(
        self,
        *,
        users: list[User],
        tokens: dict[str, str],
        dossiers: list[Dossier],
        claims: dict[tuple[str, str, str, str], Claim],
        instant: datetime | None = None,
    ) -> None:
        """Replace everything at once. Running builds are cancelled and their results dropped."""
        with self.lock:
            self.generation += 1
            for build in self.running:
                build.cancel.set()
            self.running = set()
            if instant is not None:
                self.clock.set(instant)
            self.users = {user.user_id: user for user in users}
            self.user_by_email = {user.email.casefold(): user.user_id for user in users}
            self.tokens = dict(tokens)
            self.dossiers = {dossier.domain: dossier for dossier in dossiers}
            self.claims = dict(claims)
            self.reservations = {}
            self.lock.notify_all()
