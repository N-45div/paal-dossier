"""Charging one provider call against the budget, with retries for refused calls."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .budget import Budget

ATTEMPTS = 4
# A call repeated within a second of a 429 for it is answered 429 again, so a rate-limited
# retry waits longer than that. Other refusals are retried after a short pause.
RATE_LIMIT_PAUSE_S = 1.1
OTHER_REFUSAL_PAUSE_S = 0.1


class Refused(Exception):
    """The provider refused the call with an error status. The call costs nothing."""

    def __init__(self, message: str, *, rate_limited: bool = False) -> None:
        super().__init__(message)
        self.rate_limited = rate_limited


class Unanswered(Exception):
    """The call got no answer (timeout or connection failure). The call costs its units."""


@dataclass(frozen=True)
class Outcome:
    status: str  # "answered", "refused", "unanswered" or "skipped"
    value: Any = None

    @property
    def answered(self) -> bool:
        return self.status == "answered"


SKIPPED = Outcome("skipped")
REFUSED = Outcome("refused")
UNANSWERED = Outcome("unanswered")


def perform(
    budget: Budget,
    units: int,
    call: Callable[[], Any],
    *,
    attempts: int = ATTEMPTS,
) -> Outcome:
    """Run one call that costs units. Refused calls are retried, and each refusal is refunded."""
    for attempt in range(attempts):
        if not budget.reserve(units):
            return SKIPPED
        try:
            value = call()
        except Refused as refusal:
            budget.refund(units)
            if attempt + 1 < attempts:
                time.sleep(RATE_LIMIT_PAUSE_S if refusal.rate_limited else OTHER_REFUSAL_PAUSE_S)
            continue
        except Exception:  # noqa: BLE001 - any failure without an answer is charged, never raised
            return UNANSWERED
        return Outcome("answered", value)
    return REFUSED
