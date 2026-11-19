"""A scripted gateway for strategy tests: records calls and charges units as §9 does."""

from __future__ import annotations

from dossier.engine.build import SEARCH_UNITS
from dossier.engine.providers import ERROR, OK, TIMEOUT, Answer

EXTRACT_UNIT = 1
RESEARCH_UNITS = 25


class FakeGateway:
    """``answers`` maps a call key to the Answer, or to a list consumed in order.

    Keys: ("search", query, provider, depth), ("extract", url), ("research", domain).
    A missing key answers ``ok`` with no items. Units: an error costs nothing, a timeout and
    an ok answer cost the full table cost.
    """

    def __init__(self, budget: int = 80, answers: dict | None = None) -> None:
        self.budget = budget
        self.answers = dict(answers or {})
        self.calls: list[tuple] = []
        self._spent = 0
        self._success = False

    @property
    def spent(self) -> int:
        return self._spent

    @property
    def any_success(self) -> bool:
        return self._success

    def can_call(self, units: int) -> bool:
        return self._spent + units <= self.budget

    def search(self, query, provider, depth):
        return self._call(("search", query, provider, depth), SEARCH_UNITS[(provider, depth)])

    def extract(self, urls):
        urls = list(urls)
        answer = self._call(("extract", tuple(urls)), EXTRACT_UNIT * len(urls))
        return answer

    def research(self, domain, fields):
        return self._call(("research", domain, tuple(fields)), RESEARCH_UNITS)

    def _call(self, key, units) -> Answer:
        self.calls.append(key)
        scripted = self.answers.get(key, Answer(status=OK))
        if isinstance(scripted, list):
            scripted = scripted.pop(0) if scripted else Answer(status=OK)
        if scripted.status == ERROR:
            return scripted
        self._spent += units
        if scripted.status == TIMEOUT:
            return scripted
        self._success = True
        return scripted
