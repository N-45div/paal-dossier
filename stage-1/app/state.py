"""In-process service state. One process, one event loop: each handler mutates state
without awaiting in between, so a mutation is atomic. Anything that awaits (hashing,
provider calls) must re-check state after the await."""

from __future__ import annotations

from dataclasses import dataclass, field

from aiohttp import web

from app.clock import Clock


@dataclass
class User:
    id: str
    email: str
    display_name: str
    password_hash: str


@dataclass
class State:
    """Everything a reset replaces. `generation` changes on every reset or import."""

    generation: int = 0
    users_by_id: dict[str, User] = field(default_factory=dict)
    users_by_email: dict[str, User] = field(default_factory=dict)
    # bearer token -> user id
    tokens: dict[str, str] = field(default_factory=dict)


class Store:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.state = State()

    def replace(self, new_state: State) -> None:
        """Swap in a whole new state (reset, import). Bumps the generation."""
        new_state.generation = self.state.generation + 1
        self.state = new_state


# The application key under which the Store lives.
STORE: web.AppKey[Store] = web.AppKey("store", Store)
