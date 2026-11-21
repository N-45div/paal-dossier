"""The result of one build, as the API layer consumes it (Rul-2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.support import FIELDS


@dataclass(frozen=True)
class FieldResult:
    """One field's decision: its value (None when unknown) and the excerpts that support it."""

    value: Any = None
    citations: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class BuildOutcome:
    """What one build decided.

    ``ok`` is False only when no provider call succeeded; ``spent_units`` counts every
    call the build charged, including when ``ok`` is False.
    """

    ok: bool
    spent_units: int
    fields: dict[str, FieldResult]


def unknown_fields() -> dict[str, FieldResult]:
    """All six fields unknown."""
    return {name: FieldResult() for name in FIELDS}
