"""In-process service state. One process, one event loop: each handler mutates state
without awaiting in between, so a mutation is atomic. Anything that awaits (hashing,
provider calls) must re-check state after the await."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from aiohttp import web

from app.clock import Clock
from app.research import FieldResult, unknown_fields


@dataclass
class User:
    id: str
    email: str
    display_name: str
    password_hash: str


@dataclass
class Dossier:
    """`building` is True while a build runs. `last_outcome` is the outcome of the last
    completed build ('ready' or 'failed'); it is 'failed' until a build has completed."""

    id: str
    domain: str
    building: bool = False
    last_outcome: str = "failed"
    fields: dict[str, FieldResult] = field(default_factory=unknown_fields)
    researched_at: datetime | None = None
    spent_units: int = 0

    @property
    def live_state(self) -> str:
        return "building" if self.building else self.last_outcome


@dataclass
class IdemRecord:
    """A completed idempotent request: its canonical body and the original response body."""

    canonical: object
    body: dict


@dataclass
class State:
    """Everything a reset or import replaces. `generation` changes on every replacement."""

    generation: int = 0
    users_by_id: dict[str, User] = field(default_factory=dict)
    users_by_email: dict[str, User] = field(default_factory=dict)
    # bearer token -> user id
    tokens: dict[str, str] = field(default_factory=dict)
    dossiers_by_domain: dict[str, Dossier] = field(default_factory=dict)
    # (user id, idempotency key, method, raw path) -> record
    idempotency: dict[tuple[str, str, str, str], IdemRecord] = field(default_factory=dict)


class Store:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.state = State()
        self.build_tasks: set[asyncio.Task] = set()

    def replace(self, new_state: State) -> None:
        """Swap in a whole new state (reset, import). Running builds are cancelled, and any
        build that still finishes is discarded by its generation check."""
        new_state.generation = self.state.generation + 1
        self.state = new_state
        for task in list(self.build_tasks):
            task.cancel()


# The application key under which the Store lives.
STORE: web.AppKey[Store] = web.AppKey("store", Store)
