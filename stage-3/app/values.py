"""``GET /dossiers/{domain}/values?true_at=`` over build records (stage 3, R3B).

Pure: the caller passes the ready records whose time is at or before ``as_of``, in build order.
Page versions (Two times per value): a version of a URL holds from its ``true_from``. A later
dated version of the same URL replaces every earlier version of that URL whose ``true_from`` is
on or after its own; the latest earlier version it does not replace stops holding on its
``true_from``. A version with a null ``true_from`` holds from no date and replaces every earlier
version of its URL. The six fields are decided by the stage-2 rule (``decide_field``); the
seventh, ``executives``, per title (``app.executives``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Iterable

from app.candidates import Candidate
from app.executives import decide_executives
from app.records import BuildRecord, PageVersion
from app.selection import decide_field
from app.support import FIELDS


@dataclass
class _Span:
    version: PageVersion
    end: date | None  # the first day the version no longer holds; None while it holds


def _gather(spans: list[_Span], version: PageVersion) -> list[_Span]:
    if version.true_from is None:
        return []  # holds from no date, and replaces every earlier version of its URL
    kept = [s for s in spans if s.version.true_from is not None
            and s.version.true_from < version.true_from]
    if kept:
        latest = max(kept, key=lambda s: s.version.true_from)
        latest.end = version.true_from  # overwrites any end set by a version now replaced
    return kept + [_Span(version=version, end=None)]


def holding_versions(records: Iterable[BuildRecord], true_at: date) -> list[PageVersion]:
    """Every page version that holds on ``true_at``, folded over the ready records in order."""
    by_url: dict[str, list[_Span]] = {}
    for record in records:
        if not record.ok:
            continue
        for version in record.versions:
            by_url[version.url] = _gather(by_url.get(version.url, []), version)
    holding: list[PageVersion] = []
    for spans in by_url.values():
        for span in spans:
            start = span.version.true_from
            if start is None or start > true_at:
                continue
            if span.end is None or true_at < span.end:
                holding.append(span.version)
    return holding


@dataclass(frozen=True)
class FieldAt:
    value: Any
    true_from: date | None
    citations: list[dict[str, str]]


def candidates_at(records: Iterable[BuildRecord], true_at: date) -> dict[str, list[Candidate]]:
    """Every holding version's candidates by field (seven fields), stamped with their true_from."""
    result: dict[str, list[Candidate]] = {name: [] for name in (*FIELDS, "executives")}
    for version in holding_versions(records, true_at):
        for name, found in version.candidates.items():
            if name not in result:
                continue
            result[name].extend(replace(c, true_from=version.true_from) for c in found)
    return result


def values_at(records: Iterable[BuildRecord], true_at: date) -> dict[str, FieldAt]:
    """Each field's value at ``true_at``: the selection rule over the candidates that hold."""
    candidates = candidates_at(records, true_at)
    answers: dict[str, FieldAt] = {}
    for name in FIELDS:
        decision = decide_field(candidates[name])
        answers[name] = FieldAt(
            value=decision.value,
            true_from=decision.ranked[0].true_from if decision.ranked else None,
            citations=decision.citations,
        )
    executives = decide_executives(candidates["executives"])
    answers["executives"] = FieldAt(value=executives.value, true_from=executives.true_from,
                                    citations=executives.citations)
    return answers
