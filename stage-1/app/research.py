"""Build contract between the dossier service and the research engine (Rul-2).

This module is a placeholder: every build answers all-unknown with no provider call. The
research engine (PC) replaces this file entirely and keeps these names and shapes.
"""

from __future__ import annotations

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
    """One field of a build: `value` is None and `citations` empty when unknown.

    Each citation is a dict with keys `url`, `excerpt` and `provider`."""

    value: object = None
    citations: list[dict] = field(default_factory=list)


@dataclass
class BuildOutcome:
    """`ok` is False iff no provider call succeeded. `spent_units` counts every call made."""

    ok: bool
    spent_units: int
    fields: dict[str, FieldResult]


def unknown_fields() -> dict[str, FieldResult]:
    return {name: FieldResult() for name in FIELD_NAMES}


async def run_build(domain: str) -> BuildOutcome:
    """Placeholder: research nothing, spend nothing, report failure."""
    return BuildOutcome(ok=False, spent_units=0, fields=unknown_fields())
