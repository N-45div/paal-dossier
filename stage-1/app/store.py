"""The state guard: every read and write of service state goes through this class.

One lock protects the state. Password hashing runs outside the lock; an operation that
spans a hash checks the state generation (RL9) before it writes, so a reset or import
that lands in between is never overwritten. Builds report back through `add_spend` and
`finish_build`, which drop their writes when the generation has changed.
"""

import secrets
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from .clock import Clock
from .dossiers import fields_from_engine
from .errors import email_taken, unauthenticated, validation
from .passwords import hash_fixture_passwords, hash_password, verify_password
from .state import State, state_from_json
from .validation import is_valid_display_name, is_valid_email, is_valid_password
from .wire import Moment, format_ts

_TOKEN_BYTES = 32


@dataclass(frozen=True)
class SeededUser:
    id: str
    email: str
    display_name: str
    password: str


@dataclass(frozen=True)
class Fixture:
    now: Moment
    users: list[SeededUser]


@dataclass(frozen=True)
class Account:
    user_id: str
    display_name: str
    token: str


def authenticate_in(state: State, token: str | None) -> str:
    """Resolve a bearer token against a state; callers hold the lock so the answer is current."""
    if not token:
        raise unauthenticated()
    user_id = state.tokens.get(token)
    if user_id is None or user_id not in state.users:
        raise unauthenticated("unknown bearer token")
    return user_id


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

    @contextmanager
    def transact(self) -> Iterator[tuple[State, int]]:
        """Hold the lock for a multi-step operation; yields the state and its generation."""
        with self._lock:
            yield self._state, self._generation

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
            user_id = self._state.next_id("user", self._state.users)
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
        with self._lock:
            return authenticate_in(self._state, token)

    def _issue_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        self._state.tokens[token] = user_id
        return token

    # --- builds ---------------------------------------------------------

    def add_spend(self, dossier_id: str, generation: int, units: int) -> None:
        with self._lock:
            if generation != self._generation:
                return
            record = self._record_by_id(dossier_id)
            if record is not None:
                record["spent_units"] += units

    def finish_build(self, dossier_id: str, generation: int, requested_at: Moment, result: Any, reported: int) -> None:
        """Apply a finished build (RL3): ready with its fields, or failed and fields unchanged."""
        with self._lock:
            if generation != self._generation:
                return
            record = self._record_by_id(dossier_id)
            if record is None:
                return
            if result is None or not getattr(result, "ok", False):
                record["state"] = "failed"
                record["last_state"] = "failed"
                if result is not None:
                    record["spent_units"] += max(0, int(result.spent) - reported)
                return
            # Prepare every new value before touching the record: a failure here must leave the
            # previous fields in place for the worker's fallback (RL27).
            fields = fields_from_engine(result.fields)
            researched_at = format_ts(requested_at)
            spent = record["spent_units"] + max(0, int(result.spent) - reported)
            record["spent_units"] = spent
            record["fields"] = fields
            record["researched_at"] = researched_at
            record["state"] = "ready"
            record["last_state"] = "ready"

    def fail_build(self, dossier_id: str, generation: int) -> None:
        """End a build as failed without touching its fields (the last-resort path of a worker)."""
        with self._lock:
            if generation != self._generation:
                return
            record = self._record_by_id(dossier_id)
            if record is not None:
                record["state"] = "failed"
                record["last_state"] = "failed"

    def _record_by_id(self, dossier_id: str) -> dict | None:
        for record in self._state.dossiers.values():
            if record["dossier_id"] == dossier_id:
                return record
        return None

    # --- control: reset, export, import ---------------------------------

    def reset(self, fixture: Fixture) -> None:
        """Replace all state with the fixture and set the clock to its `now`."""
        fresh = State()
        digests = hash_fixture_passwords([seeded.password for seeded in fixture.users])
        for seeded, digest in zip(fixture.users, digests):
            fresh.add_user(seeded.id, seeded.email, seeded.display_name, digest)
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
