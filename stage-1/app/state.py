"""In-memory service state. All mutation happens synchronously on the event loop."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any

from .fields import unknown_fields


@dataclass
class User:
    user_id: str
    email: str
    display_name: str
    password_hash: str


@dataclass
class Dossier:
    dossier_id: str
    domain: str
    fields: dict[str, dict[str, Any]] = field(default_factory=unknown_fields)
    outcome: str | None = None  # outcome of the last completed build: "ready" / "failed"
    building: bool = False
    researched_at: str | None = None
    spent_units: int = 0  # cost of every completed build
    running_spent: int = 0  # cost so far of the build in progress

    @property
    def state(self) -> str:
        if self.building:
            return "building"
        return self.outcome or "failed"

    @property
    def total_spent(self) -> int:
        return self.spent_units + self.running_spent


@dataclass
class IdempotentResponse:
    body: str  # canonical JSON text of the request body
    response: Any


class Store:
    """Users, sessions, dossiers and stored idempotent responses."""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.user_by_email: dict[str, str] = {}
        self.tokens: dict[str, str] = {}
        self.dossiers: dict[str, Dossier] = {}  # by normalised domain
        self.idempotency: dict[tuple[str, str, str, str], IdempotentResponse] = {}

    def add_user(self, user: User) -> None:
        self.users[user.user_id] = user
        self.user_by_email[user.email.lower()] = user.user_id

    def issue_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens[token] = user_id
        return token

    def new_dossier(self, domain: str) -> Dossier:
        dossier = Dossier(dossier_id="d_" + secrets.token_hex(8), domain=domain)
        self.dossiers[domain] = dossier
        return dossier
