"""Budget ledger: units are reserved before a call and settled when its outcome is known (RL5)."""

from __future__ import annotations

import threading
from typing import Callable, Optional


class Ledger:
    """Thread-safe accounting of one build's units. Never lets spent + reserved exceed budget."""

    def __init__(self, budget: int, on_spend: Optional[Callable[[int], None]] = None) -> None:
        self._budget = budget
        self._on_spend = on_spend
        self._lock = threading.Lock()
        self._spent = 0
        self._reserved = 0

    @property
    def spent(self) -> int:
        with self._lock:
            return self._spent

    def reserve(self, units: int, keep: int = 0) -> bool:
        """Reserve units if they fit while keeping ``keep`` units free for later calls."""
        with self._lock:
            if self._spent + self._reserved + units > self._budget - keep:
                return False
            self._reserved += units
            return True

    def settle(self, reserved: int, charged: int) -> None:
        """Release a reservation and record what the call actually cost."""
        with self._lock:
            self._reserved -= reserved
            self._spent += charged
        if charged > 0 and self._on_spend is not None:
            try:
                self._on_spend(charged)
            except Exception:  # the app's bookkeeping must never break a build
                pass
