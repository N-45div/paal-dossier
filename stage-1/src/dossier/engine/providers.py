"""What the build strategy needs from the provider gateway (P4a).

The gateway owns WebRouter, the unit budget and the deadline. The strategy in ``build.py``
asks ``can_call`` before each call and reads each answer's ``status``:

- ``ok``: the provider answered; ``items`` holds the pages or claims it served.
- ``error``: the provider refused with an error status; it cost nothing.
- ``timeout``: the answer did not arrive; the full cost is charged.
- ``skipped``: the gateway did not call (budget, deadline or cancel); nothing is charged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

OK = "ok"
ERROR = "error"
TIMEOUT = "timeout"
SKIPPED = "skipped"


@dataclass(frozen=True)
class Page:
    """A page a provider served: its full (or truncated) text, with the serving provider."""

    url: str
    title: str
    text: str
    provider: str


@dataclass(frozen=True)
class Claim:
    """A research answer: a claimed value for ``field``, with the citation it names."""

    field: str
    value: Any
    url: str
    excerpt: str
    provider: str


@dataclass(frozen=True)
class Answer:
    """One provider call's outcome: a status and the items it served."""

    status: str
    items: tuple = ()


class Gateway(Protocol):
    """Provider access as the strategy sees it. Units are reserved by the gateway."""

    @property
    def spent(self) -> int: ...

    @property
    def any_success(self) -> bool: ...

    def can_call(self, units: int) -> bool: ...

    def search(self, query: str, provider: str, depth: str) -> Answer:
        """Search ``query`` through ``provider`` (``nimble`` or ``tavily``) at ``depth``."""
        ...

    def extract(self, urls: list[str]) -> Answer:
        """Extract the full text of ``urls`` through nimble (no ``render``)."""
        ...

    def research(self, domain: str, fields: list[str]) -> Answer:
        """Run one nimble research for ``domain`` asking for ``fields``."""
        ...
