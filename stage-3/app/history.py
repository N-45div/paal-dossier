"""Derived views of build records (stage 3): selected values with their two times, history
entries, and the change-feed entries a build adds. Every function here is pure over a list of
BuildRecords in build order, so the same records always give the same answers.

Learned times (Two times per value): a candidate's `learned_at` is the time of the first ready
build that gathered it with the same field, value, URL, provider and title. A selected value's
`learned_at` is the time of the build that made it the selected value; it is carried forward
while the selected value stays the same."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.candidates import Candidate, normalise_value
from app.records import BuildRecord
from app.selection import decide_field
from app.support import FIELDS

@dataclass(frozen=True)
class Selected:
    """A field's selected value after one build, with its two times and evidence."""

    field: str
    value: Any
    status: str
    true_from: date | None
    learned_at: datetime | None
    citations: tuple[dict[str, str], ...]
    # Every distinct candidate in rank order, each with its own learned_at.
    ranked: tuple[tuple[Candidate, datetime | None], ...]


@dataclass(frozen=True)
class Entry:
    """A history entry, or a feed entry when `type` is `change` or `correction`."""

    field: str
    type: str  # "initial" | "change" | "correction"
    previous: Any
    value: Any
    true_from: date | None
    learned_at: datetime | None
    citations: tuple[dict[str, str], ...]


def _key(name: str, candidate: Candidate) -> tuple:
    return (name, normalise_value(candidate.value), candidate.url, candidate.provider,
            candidate.title)


def views(records: list[BuildRecord]) -> list[tuple[BuildRecord, dict[str, Selected]]]:
    """For each ready record in build order: the selected value of every field after it."""
    first_seen: dict[tuple, datetime] = {}
    carried: dict[str, tuple[Any, datetime | None]] = {}
    result = []
    for record in records:
        if not record.ok:
            continue
        gathered = record.candidates()
        for name, found in gathered.items():
            for candidate in found:
                first_seen.setdefault(_key(name, candidate), record.time)
        selected: dict[str, Selected] = {}
        for name in FIELDS:
            found = gathered.get(name, [])
            decision = decide_field(found)
            value = decision.value
            previous_value, previous_learned = carried.get(name, (None, None))
            if value is None:
                learned = None
            elif value == previous_value:
                learned = previous_learned
            else:
                learned = record.time
            carried[name] = (value, learned)
            ranked = tuple(
                (candidate, first_seen.get(_key(name, candidate)))
                for candidate in decision.ranked
            )
            selected[name] = Selected(
                field=name, value=value, status=decision.status,
                true_from=_true_from(decision), learned_at=learned,
                citations=tuple(decision.citations) if value is not None else (),
                ranked=ranked,
            )
        result.append((record, selected))
    return result


def _true_from(decision: Any) -> date | None:
    """The selected value's true_from: that of its selected (first ranked) candidate."""
    if not decision.ranked or decision.value is None:
        return None
    return decision.ranked[0].true_from


def differs(previous: Selected | None, new: Selected) -> bool:
    before = previous.value if previous is not None else None
    return before != new.value


def classify(previous: Selected | None, new: Selected) -> str:
    """Spec 'Changes and corrections': a correction when both values are not null and the new
    value's true_from is on or before the earlier one's (both non-null); otherwise a change."""
    if (previous is not None and previous.value is not None and new.value is not None
            and previous.true_from is not None and new.true_from is not None
            and new.true_from <= previous.true_from):
        return "correction"
    return "change"


def build_entries(previous: dict[str, Selected] | None,
                  current: dict[str, Selected], first: bool) -> list[Entry]:
    """The entries one ready build adds, in FIELDS order. `first` marks the dossier's first ready
    build: each field with a value there gets an `initial` entry and no feed entry."""
    entries = []
    for name in FIELDS:
        new = current[name]
        before = previous.get(name) if previous is not None else None
        if first:
            if new.value is not None:
                entries.append(_entry(name, "initial", None, new))
            continue
        if not differs(before, new):
            continue
        kind = classify(before, new)
        entries.append(_entry(name, kind, before.value if before is not None else None, new))
    return entries


def _entry(name: str, kind: str, previous: Any, new: Selected) -> Entry:
    return Entry(
        field=name, type=kind, previous=previous, value=new.value,
        true_from=new.true_from if new.value is not None else None,
        learned_at=new.learned_at if new.value is not None else None,
        citations=new.citations if new.value is not None else (),
    )


def history(records: list[BuildRecord]) -> dict[str, list[Entry]]:
    """Every field's history, oldest first: the entries of every ready build in order."""
    result: dict[str, list[Entry]] = {name: [] for name in FIELDS}
    previous: dict[str, Selected] | None = None
    for _, current in views(records):
        for entry in build_entries(previous, current, first=previous is None):
            result[entry.field].append(entry)
        previous = current
    return result


def feed_entries(previous: dict[str, Selected] | None, current: dict[str, Selected],
                 first: bool) -> list[Entry]:
    """The change-feed entries a build adds: its `change` and `correction` entries."""
    return [entry for entry in build_entries(previous, current, first)
            if entry.type != "initial"]


def unknown_views() -> dict[str, Selected]:
    """Every field unknown: the view of a dossier with no completed ready build."""
    return {name: Selected(field=name, value=None, status="unknown", true_from=None,
                           learned_at=None, citations=(), ranked=())
            for name in FIELDS}


def snapshot_at(records: list[BuildRecord], as_of: datetime
                ) -> tuple[BuildRecord, dict[str, Selected], int] | None:
    """The dossier as it stood at `as_of` (stage 3, `?as_of=`): the latest ready build whose time
    is at or before `as_of` (ties go to the later build), its selected values as the builds up
    to it give them, and the spending of every build at or before `as_of`. None when no ready
    build qualifies."""
    eligible = [r for r in records if r.ok and r.time <= as_of]
    if not eligible:
        return None
    chosen = max(eligible, key=lambda r: (r.time, r.index))
    prefix = [r for r in records if r.time <= as_of and r.index <= chosen.index]
    for record, selected in reversed(views(prefix)):
        if record is chosen:
            spent = sum(r.spent_units for r in records if r.time <= as_of)
            return chosen, selected, spent
    return None
