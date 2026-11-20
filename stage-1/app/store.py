"""In-memory state behind one re-entrant lock: users, tokens, dossiers and idempotency records.

Hold `Store.lock` around any sequence of reads and writes that must be atomic. Threads waiting
for an in-flight idempotent request wait on `Store.changed`, which shares that lock.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from typing import Any

from .dossier_model import Dossier
from .validation import new_id

IdempotencyKey = tuple[str, str, str, str]  # user id, method, raw path, Idempotency-Key


@dataclass(frozen=True)
class User:
    id: str
    email: str
    display_name: str
    password_hash: str


@dataclass
class IdempotencyEntry:
    fingerprint: str | None  # canonical JSON of the request's `domain`, or None when absent
    reply: tuple[int, Any] | None = None  # (status, body) once a 2xx reply is stored


@dataclass
class StoreState:
    """Everything the service holds; used to replace the store wholesale (reset, import)."""

    users: list[User] = field(default_factory=list)
    tokens: dict[str, str] = field(default_factory=dict)  # token -> user id
    dossiers: list[Dossier] = field(default_factory=list)
    idempotency: dict[IdempotencyKey, IdempotencyEntry] = field(default_factory=dict)


class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self._users: dict[str, User] = {}
        self._user_id_by_email: dict[str, str] = {}
        self._user_id_by_token: dict[str, str] = {}
        self._dossiers: dict[str, Dossier] = {}
        self._dossier_id_by_domain: dict[str, str] = {}
        self._idempotency: dict[IdempotencyKey, IdempotencyEntry] = {}
        self._generation = 0

    @property
    def generation(self) -> int:
        """Bumped by every reset and import; background work compares it to detect them."""
        with self.lock:
            return self._generation

    def replace(self, state: StoreState) -> None:
        """Atomically make `state` the whole content of the store. Callers validate it first."""
        with self.lock:
            self._users = {}
            self._user_id_by_email = {}
            self._dossiers = {}
            self._dossier_id_by_domain = {}
            for user in state.users:
                self.add_user(user)
            self._user_id_by_token = dict(state.tokens)
            for dossier in state.dossiers:
                self._insert_dossier(dossier)
            self._idempotency = dict(state.idempotency)
            self._generation += 1
            self.changed.notify_all()

    def state(self) -> StoreState:
        """The live content (shallow copies of the containers); read it while holding the lock."""
        with self.lock:
            return StoreState(
                users=list(self._users.values()),
                tokens=dict(self._user_id_by_token),
                dossiers=list(self._dossiers.values()),
                idempotency=dict(self._idempotency),
            )

    def user_by_id(self, user_id: str) -> User | None:
        with self.lock:
            return self._users.get(user_id)

    def user_by_email(self, email: str) -> User | None:
        with self.lock:
            user_id = self._user_id_by_email.get(email)
            return None if user_id is None else self._users.get(user_id)

    def user_by_token(self, token: str) -> User | None:
        with self.lock:
            user_id = self._user_id_by_token.get(token)
            return None if user_id is None else self._users.get(user_id)

    def add_user(self, user: User) -> None:
        with self.lock:
            if user.id in self._users or user.email in self._user_id_by_email:
                raise ValueError(f"user {user.id} or email {user.email} already exists")
            self._users[user.id] = user
            self._user_id_by_email[user.email] = user.id

    def issue_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock:
            self._user_id_by_token[token] = user_id
        return token

    def dossier_by_id(self, dossier_id: str) -> Dossier | None:
        with self.lock:
            return self._dossiers.get(dossier_id)

    def dossier_by_domain(self, domain: str) -> Dossier | None:
        with self.lock:
            dossier_id = self._dossier_id_by_domain.get(domain)
            return None if dossier_id is None else self._dossiers.get(dossier_id)

    def dossiers(self) -> list[Dossier]:
        with self.lock:
            return list(self._dossiers.values())

    def add_dossier(self, domain: str) -> Dossier:
        with self.lock:
            dossier = Dossier(dossier_id=new_id("d"), domain=domain)
            self._insert_dossier(dossier)
            return dossier

    def _insert_dossier(self, dossier: Dossier) -> None:
        if dossier.dossier_id in self._dossiers or dossier.domain in self._dossier_id_by_domain:
            raise ValueError(f"dossier {dossier.dossier_id} or domain {dossier.domain} exists")
        self._dossiers[dossier.dossier_id] = dossier
        self._dossier_id_by_domain[dossier.domain] = dossier.dossier_id

    def idempotency_entry(self, key: IdempotencyKey) -> IdempotencyEntry | None:
        with self.lock:
            return self._idempotency.get(key)

    def put_idempotency(self, key: IdempotencyKey, entry: IdempotencyEntry) -> None:
        with self.lock:
            self._idempotency[key] = entry

    def drop_idempotency(self, key: IdempotencyKey, entry: IdempotencyEntry) -> None:
        """Forget a claim that did not end in a 2xx reply, if it is still the current one."""
        with self.lock:
            if self._idempotency.get(key) is entry:
                del self._idempotency[key]
