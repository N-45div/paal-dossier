"""The state guard: every read and write of service state goes through this class.

One lock protects the state. Password hashing runs outside the lock; any operation
that spans a hash checks the state generation (RL9) before it writes, so a reset or
import that lands in between is never overwritten by an older result.
"""

import secrets
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .clock import Clock
from .errors import email_taken, unauthenticated, validation
from .passwords import hash_password, verify_password
from .state import State, state_from_json
from .validation import is_valid_display_name, is_valid_email, is_valid_password

_TOKEN_BYTES = 32


@dataclass(frozen=True)
class SeededUser:
    id: str
    email: str
    display_name: str
    password: str


@dataclass(frozen=True)
class Fixture:
    now: datetime
    users: list[SeededUser]


@dataclass(frozen=True)
class Account:
    user_id: str
    display_name: str
    token: str


class Store:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._state = State()
        self._generation = 0

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    # --- accounts -------------------------------------------------------

    def signup(self, email: str, password: str, display_name: str) -> Account:
        if not is_valid_email(email):
            raise validation("email must be of the form local@domain")
        if not is_valid_password(password):
            raise validation("password must be at least 8 characters")
        if not is_valid_display_name(display_name):
            raise validation("display_name must be 1 to 100 characters")
        encoded = hash_password(password)
        with self._lock:
            if email.lower() in self._state.emails:
                raise email_taken()
            user_id = self._state.next_id("user", "u_")
            self._state.add_user(user_id, email, display_name, encoded)
            token = self._issue_token(user_id)
        return Account(user_id, display_name, token)

    def login(self, email: str, password: str) -> Account:
        # Look up under the lock, verify outside it, then confirm the state did not change.
        while True:
            with self._lock:
                generation = self._generation
                user_id = self._state.emails.get(email.lower())
                if user_id is None:
                    raise unauthenticated("wrong email or password")
                user = dict(self._state.users[user_id])
            if not verify_password(password, user["password_hash"]):
                raise unauthenticated("wrong email or password")
            with self._lock:
                if generation != self._generation:
                    continue
                token = self._issue_token(user_id)
                return Account(user_id, user["display_name"], token)

    def authenticate(self, token: str | None) -> str:
        """The user id behind a bearer token; 401 for a missing or unknown token."""
        if not token:
            raise unauthenticated()
        with self._lock:
            user_id = self._state.tokens.get(token)
            if user_id is None or user_id not in self._state.users:
                raise unauthenticated("unknown bearer token")
            return user_id

    def _issue_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        self._state.tokens[token] = user_id
        return token

    # --- control: reset, clock, export, import ---------------------------

    def reset(self, fixture: Fixture) -> None:
        """Replace all state with the fixture and set the clock to its `now`."""
        fresh = State()
        for seeded in fixture.users:
            fresh.add_user(seeded.id, seeded.email, seeded.display_name, hash_password(seeded.password))
        with self._lock:
            self._state = fresh
            self._generation += 1
            self._clock.set_fixed(fixture.now)

    def export_state(self) -> dict[str, Any]:
        with self._lock:
            return self._state.to_json()

    def import_state(self, obj: Any) -> None:
        """Validate fully before touching anything, then swap the state atomically."""
        replacement = state_from_json(obj)
        with self._lock:
            self._state = replacement
            self._generation += 1
