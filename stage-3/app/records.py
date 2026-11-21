"""Build records (stage 3, Rul-S3-1): what each build gathered and decided, as plain data.

A dossier's history, change feed, ``as_of`` and ``values`` are folds over its ordered
``BuildRecord``s, so nothing derived is stored. This module holds types only; it does no IO.

- ``PageVersion``: what one ready build gathered from one URL: its candidates and its
  ``true_from``. A gathered URL with no candidates still has a version.
- ``FieldSnapshot``: one field's selected value as the build decided it, with its status,
  citations and candidates. ``learned_at`` is filled by the history fold (None in a record).
- ``BuildRecord``: one build of one dossier. ``ok`` is True for a ``ready`` build; a failed
  build keeps ``spent_units`` and has no versions or fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.candidates import Candidate


@dataclass(frozen=True)
class PageVersion:
    url: str
    true_from: date | None
    candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class FieldSnapshot:
    name: str
    value: Any
    status: str  # "known" | "contested" | "unknown"
    true_from: date | None = None
    learned_at: datetime | None = None
    citations: tuple[dict[str, str], ...] = ()
    candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class BuildRecord:
    index: int
    time: datetime
    ok: bool
    spent_units: int
    versions: tuple[PageVersion, ...] = ()
    fields: dict[str, FieldSnapshot] = field(default_factory=dict)
