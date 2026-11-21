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


class Ledger:
    """Spending of one build against its limit."""

    def __init__(self, limit: int = BUILD_BUDGET_UNITS) -> None:
        self.limit = limit
        self.spent = 0

    def reserve(self, cost: int) -> bool:
        """Charge ``cost`` if it fits under the limit; False leaves the ledger unchanged."""
        if self.spent + cost > self.limit:
            return False
        self.spent += cost
        return True

    def release(self, cost: int) -> None:
        """Give back the reservation of a call that was refused and charged nothing."""
        self.spent = max(0, self.spent - cost)
