"""The result of one research build, as the dossier service consumes it."""

from dataclasses import dataclass, field

from .fields import FIELDS


def unknown_fields() -> dict[str, dict]:
    """All six fields unknown: value None and no citations."""
    return {name: {"value": None, "citations": []} for name in FIELDS}


@dataclass(frozen=True)
class BuildOutcome:
    ok: bool
    fields: dict[str, dict] = field(default_factory=unknown_fields)
    spent_units: int = 0


def failed_outcome(spent_units: int = 0) -> BuildOutcome:
    return BuildOutcome(ok=False, fields=unknown_fields(), spent_units=spent_units)
