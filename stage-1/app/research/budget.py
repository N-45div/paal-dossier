"""Unit budget of one build: reserve before a call, give back when refused."""
from __future__ import annotations

from .config import BUILD_BUDGET_UNITS


class Budget:
    def __init__(self, cap: int = BUILD_BUDGET_UNITS) -> None:
        self.cap = cap
        self.committed = 0

    def reserve(self, units: int) -> bool:
        """Commit ``units`` if the build stays within its cap."""
        if self.committed + units > self.cap:
            return False
        self.committed += units
        return True

    def release(self, units: int) -> None:
        self.committed -= units

    @property
    def remaining(self) -> int:
        return self.cap - self.committed
