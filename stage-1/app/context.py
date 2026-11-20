"""The state every request shares: the clock and the store."""

from __future__ import annotations

from dataclasses import dataclass

from .clock import Clock
from .store import Store


@dataclass(frozen=True)
class App:
    clock: Clock
    store: Store


def create_app() -> App:
    return App(clock=Clock(), store=Store())
