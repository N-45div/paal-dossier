"""Adapters from a build's decided candidates to build records (stage 3, Rul-S3-1). Pure.

``field_snapshots`` decides the seven fields (six by the stage-2 rule, executives per title)
and returns one ``FieldSnapshot`` each. ``build_record`` turns a build's candidates and the
URLs it gathered into one ``BuildRecord``: one ``PageVersion`` per gathered URL, including a URL
with no candidates. A failed build keeps only its spending.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Sequence

from app.candidates import Candidate
from app.executives import decide_executives
from app.records import BuildRecord, FieldSnapshot, PageVersion
from app.selection import decide
from app.support import FIELDS


def field_snapshots(candidates: dict[str, list[Candidate]]) -> dict[str, FieldSnapshot]:
    """The seven fields' decisions, keyed by field name (six fields, then executives)."""
    snapshots: dict[str, FieldSnapshot] = {}
    for name, decision in decide({n: candidates.get(n, []) for n in FIELDS}).items():
        snapshots[name] = FieldSnapshot(
            name=name,
            value=decision.value,
            status=decision.status,
            true_from=decision.ranked[0].true_from if decision.ranked else None,
            citations=tuple(decision.citations),
            candidates=decision.ranked,
        )
    executives = decide_executives(candidates.get("executives", []))
    snapshots["executives"] = FieldSnapshot(
        name="executives",
        value=executives.value,
        status=executives.status,
        true_from=executives.true_from,
        citations=tuple(executives.citations),
        candidates=executives.ranked,
    )
    return snapshots


def build_record(
    index: int,
    time: datetime,
    ok: bool,
    spent_units: int,
    candidates: dict[str, list[Candidate]],
    gathered: Sequence[tuple[str, date | None]],
) -> BuildRecord:
    """One build's record. ``gathered`` is each URL the build read, in gather order, with the
    ``true_from`` of that page version (None when the page has no date)."""
    if not ok:
        return BuildRecord(index=index, time=time, ok=False, spent_units=spent_units)
    everything = [c for found in candidates.values() for c in found]
    versions: list[PageVersion] = []
    seen: set[str] = set()
    for url, true_from in gathered:
        if url in seen:
            continue
        seen.add(url)
        here = tuple(c for c in everything if c.url == url)
        versions.append(PageVersion(url=url, true_from=true_from, candidates=here))
    return BuildRecord(index=index, time=time, ok=True, spent_units=spent_units,
                       versions=tuple(versions), fields=field_snapshots(candidates))
