"""Result types of a build (RL1.3): one decided field and the whole build outcome."""

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
    """One decided field: ``value`` is None when unknown, ``citations`` are dicts with
    ``url``, ``excerpt`` and ``provider``."""

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
