"""Build engine for dossiers (RL1.3 contract).

``run_build`` researches one company through WebRouter and returns a
``BuildResult``. It never raises, never touches the clock, HTTP layer or
store, and stops early when ``cancel`` is set.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

FIELD_NAMES: tuple[str, ...] = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)


@dataclass
class FieldResult:
    """One decided field: ``value`` is None when unknown."""

    value: str | int | None = None
    citations: list[dict] = field(default_factory=list)


@dataclass
class BuildResult:
    """Outcome of one build. ``ok`` is False when no provider call succeeded."""

    ok: bool
    spent_units: int
    fields: dict[str, FieldResult]


def unknown_fields() -> dict[str, FieldResult]:
    """Six unknown fields, the result of a build that learnt nothing."""
    return {name: FieldResult(None, []) for name in FIELD_NAMES}


def run_build(domain: str, cancel: threading.Event) -> BuildResult:
    """Research ``domain``. Placeholder until the real strategy lands."""
    return BuildResult(ok=False, spent_units=0, fields=unknown_fields())
