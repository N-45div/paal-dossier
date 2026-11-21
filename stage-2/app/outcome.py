"""The result of one build, as the API layer consumes it (Rul-2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.candidates import Candidate, from_citation
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
    # Stage 2 (Rul-S2-1): every candidate per field. None means the research engine has
    # not produced candidates yet; candidates_of() then derives them from ``fields``.
    candidates: dict[str, list[Candidate]] | None = None


def unknown_fields() -> dict[str, FieldResult]:
    """All six fields unknown."""
    return {name: FieldResult() for name in FIELDS}


def candidates_of(outcome: BuildOutcome) -> dict[str, list[Candidate]]:
    """Every field's candidates for ``outcome``.

    An outcome without candidates (the stage-1 research contract) yields one candidate per
    citation of each known field, so the selection rule sees the same evidence."""
    if outcome.candidates is not None:
        return {name: list(outcome.candidates.get(name, [])) for name in FIELDS}
    return {
        name: [
            from_citation(outcome.fields[name].value, citation)
            for citation in outcome.fields[name].citations
        ] if outcome.fields[name].value is not None else []
        for name in FIELDS
    }
