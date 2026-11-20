"""In-memory state behind one re-entrant lock.

Callers that need several reads and writes to be atomic hold `Store.lock` around them.
"""

from __future__ import annotations

import secrets
import threading
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: str
    email: str
    display_name: str
    password_hash: str


class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._users: dict[str, User] = {}
        self._user_id_by_email: dict[str, str] = {}
        self._user_id_by_token: dict[str, str] = {}
        self._generation = 0

    @property
    def generation(self) -> int:
        """Bumped by every reset; background work compares it to detect a reset."""
        with self.lock:
            return self._generation

    def reset(self, users: Iterable[User]) -> None:
        with self.lock:
            self._users.clear()
            self._user_id_by_email.clear()
            self._user_id_by_token.clear()
            for user in users:
                self.add_user(user)
            self._generation += 1

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
