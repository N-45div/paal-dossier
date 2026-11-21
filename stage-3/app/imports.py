"""Stage-3 import converters (R3C): one exported dossier to build records and history seeds.

Pure: no IO. The exported dossier object is validated by the stage-1 and stage-2 readers in
``app.snapshot``; this module only turns what they read into records.

- A stage-1 export (Rul-S2-2) records no page texts: each dossier counts as one build that
  completed ready at its ``researched_at``, with one page version per cited URL. Its
  candidates have no ``true_from``.
- A stage-2 export holds the candidates of its last ready build. It counts as one build at
  ``researched_at``. A page version's ``true_from`` is the UTC date of the candidate's
  ``published_at``, since the export does not record ``Effective`` lines.
- A dossier that was not ready, or whose ``researched_at`` is null, has no records (every
  ``as_of`` is 404 for it).
- Each field with a value gets one ``initial`` history seed at ``researched_at``, with a null
  ``true_from``, as Upgrades requires.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Any

from app.build_records import build_record, field_snapshots
from app.candidates import Candidate
from app.records import BuildRecord
from app.snapshot import _stage1_candidates, _stage2_candidates


@dataclass(frozen=True)
class HistorySeed:
    field: str
    value: Any
    learned_at: datetime
    citations: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class ImportedDossier:
    records: tuple[BuildRecord, ...]
    seeds: tuple[HistorySeed, ...]


def import_stage1(item: dict[str, Any], domain: str) -> ImportedDossier:
    candidates = _stage1_candidates(item, domain)
    researched = _researched_at(item)
    if researched is None or item.get("state") != "ready":
        return ImportedDossier(records=(), seeds=_seeds(candidates, None))
    gathered = _distinct_urls(candidates)
    record = build_record(1, researched, True, _spent(item), candidates, gathered)
    return ImportedDossier(records=(record,), seeds=_seeds(candidates, researched))


def import_stage2(item: dict[str, Any], domain: str) -> ImportedDossier:
    candidates = {name: [replace(c, true_from=_utc_date(c)) for c in found]
                  for name, found in _stage2_candidates(item, domain).items()}
    researched = _researched_at(item)
    if researched is None or item.get("state") != "ready":
        return ImportedDossier(records=(), seeds=_seeds(candidates, None))
    gathered = _distinct_urls(candidates)
    record = build_record(1, researched, True, _spent(item), candidates, gathered)
    return ImportedDossier(records=(record,), seeds=_seeds(candidates, researched))


def _researched_at(item: dict[str, Any]) -> datetime | None:
    value = item.get("researched_at")
    return datetime.fromisoformat(value) if isinstance(value, str) else None


def _spent(item: dict[str, Any]) -> int:
    return int(item.get("spent_units") or 0)


def _utc_date(candidate: Candidate) -> date | None:
    if candidate.published_at is None:
        return None
    return datetime.fromisoformat(candidate.published_at).astimezone(timezone.utc).date()


def _distinct_urls(candidates: dict[str, list[Candidate]]) -> list[tuple[str, date | None]]:
    gathered: dict[str, date | None] = {}
    for found in candidates.values():
        for candidate in found:
            gathered.setdefault(candidate.url, candidate.true_from)
    return list(gathered.items())


def _seeds(candidates: dict[str, list[Candidate]], learned_at: datetime | None) -> tuple[HistorySeed, ...]:
    if learned_at is None:
        return ()
    seeds = []
    for name, snapshot in field_snapshots(candidates).items():
        if snapshot.value is None:
            continue
        seeds.append(HistorySeed(field=name, value=snapshot.value, learned_at=learned_at,
                                 citations=snapshot.citations))
    return tuple(seeds)
