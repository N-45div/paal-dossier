"""Stage-3 import converters (R3C): one exported dossier to its build record. Pure.

The exported dossier object is validated by the stage-1 and stage-2 readers in ``app.snapshot``;
this module turns what they read into a ``BuildRecord``.

- A stage-1 export (Rul-S2-2) records no page texts: its dossier counts as one build that
  completed ready at its ``researched_at``, with one page version per cited URL, no ``true_from``.
- A stage-2 export holds the candidates of its last ready build: one build at ``researched_at``.
  A page version's ``true_from`` is the UTC date of its candidates' ``published_at``, since the
  export does not record ``Effective`` lines.
- A dossier that was not ready, or whose ``researched_at`` is null, has no record (every
  ``as_of`` is 404 for it). History is derived from records, so no seeds are stored.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any

from app.candidates import Candidate
from app.records import BuildRecord, versions_of
from app.snapshot import _stage1_candidates, _stage2_candidates
from app.support import FIELDS


def import_stage1(item: dict[str, Any], domain: str) -> tuple[BuildRecord, ...]:
    return _one_build(item, _stage1_candidates(item, domain), stage2=False)


def import_stage2(item: dict[str, Any], domain: str) -> tuple[BuildRecord, ...]:
    raw = _stage2_candidates(item, domain)
    stamped = {name: [replace(c, true_from=_utc_date(c)) for c in found] for name, found in raw.items()}
    return _one_build(item, stamped, stage2=True)


def _one_build(item: dict[str, Any], candidates: dict[str, list[Candidate]],
               stage2: bool) -> tuple[BuildRecord, ...]:
    researched = _researched_at(item)
    if researched is None or item.get("state") != "ready":
        return ()
    everything = {name: list(candidates.get(name, [])) for name in (*FIELDS, "executives")}
    pages = _pages(everything, stage2)
    return (BuildRecord(index=1, time=researched, ok=True, spent_units=_spent(item),
                        versions=versions_of(everything, pages)),)


def _pages(candidates: dict[str, list[Candidate]], stage2: bool) -> dict[str, date | None]:
    pages: dict[str, date | None] = {}
    for found in candidates.values():
        for candidate in found:
            pages.setdefault(candidate.url, candidate.true_from if stage2 else None)
    return pages


def _researched_at(item: dict[str, Any]) -> datetime | None:
    value = item.get("researched_at")
    return datetime.fromisoformat(value) if isinstance(value, str) else None


def _spent(item: dict[str, Any]) -> int:
    return int(item.get("spent_units") or 0)


def _utc_date(candidate: Candidate) -> date | None:
    if candidate.published_at is None:
        return None
    return datetime.fromisoformat(candidate.published_at).astimezone(timezone.utc).date()
