"""The unit ledger of one build (Rul-3, §9).

A call's cost is reserved before the call is issued. A call that a provider refuses
with an error status is released again; every other call keeps its reservation,
because the provider may have served it. Mutations are synchronous, so the event
loop never interleaves two of them.
"""

BUILD_BUDGET_UNITS = 80

NIMBLE_SEARCH_LITE_UNITS = 1
NIMBLE_EXTRACT_UNITS = 1
NIMBLE_RESEARCH_UNITS = 25


class SharedBudget:
    """The one counter a batch's builds share (Rul-S4-4). A call is made only when it fits under
    the batch's limit, and its cost is recorded at once, so the builds never overspend together."""

    def __init__(self, limit: int, spent: int = 0) -> None:
        self.limit = limit
        self.spent = spent

    def reserve(self, cost: int) -> bool:
        if self.spent + cost > self.limit:
            return False
        self.spent += cost
        return True

    def release(self, cost: int) -> None:
        self.spent = max(0, self.spent - cost)


class Ledger:
    """Spending of one build against its limit, and against the batch's shared budget when the
    build belongs to a batch."""

    def __init__(self, limit: int = BUILD_BUDGET_UNITS, shared: SharedBudget | None = None) -> None:
        self.limit = limit
        self.spent = 0
        self.shared = shared

    def reserve(self, cost: int) -> bool:
        """Charge ``cost`` if it fits under both limits; False leaves the ledger unchanged."""
        if self.spent + cost > self.limit:
            return False
        if self.shared is not None and not self.shared.reserve(cost):
            return False
        self.spent += cost
        return True

    def release(self, cost: int) -> None:
        """Give back the reservation of a call that was refused and charged nothing."""
        self.spent = max(0, self.spent - cost)
        if self.shared is not None:
            self.shared.release(cost)
