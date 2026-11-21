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
from app.executives import decide_executives
from app.records import BuildRecord
from app.selection import decide_field
from app.investors import decide_investors, url_host
from app.support import FIELDS

# The seven fields of a dossier (stage 3): the six of stage 1, then executives.
SEVEN: tuple[str, ...] = (*FIELDS, "executives", "investors")

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
        for name in SEVEN:
            found = gathered.get(name, [])
            decision = _decide(name, found)
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
                true_from=decision.true_from, learned_at=learned,
                citations=tuple(decision.citations) if value is not None else (),
                ranked=ranked,
            )
        result.append((record, selected))
    return result


def _decide(name: str, found: list[Candidate]) -> Any:
    """The field's decision: the stage-2 rule for the six fields, the per-title rule for
    executives. Each has value, status, citations, ranked and true_from."""
    if name == "executives":
        return decide_executives(found)
    if name == "investors":
        return decide_investors(found, url_host)
    return _SixDecision(decide_field(found))


@dataclass(frozen=True)
class _SixDecision:
    """A six-field decision with its true_from: that of its selected (first ranked) candidate."""

    inner: Any

    @property
    def value(self) -> Any:
        return self.inner.value

    @property
    def status(self) -> str:
        return self.inner.status

    @property
    def citations(self) -> list[dict[str, str]]:
        return self.inner.citations

    @property
    def ranked(self) -> tuple[Candidate, ...]:
        return self.inner.ranked

    @property
    def true_from(self) -> date | None:
        if not self.inner.ranked or self.inner.value is None:
            return None
        return self.inner.ranked[0].true_from


def differs(previous: Selected | None, new: Selected) -> bool:
    before = previous.value if previous is not None else None
    return before != new.value


def _members(selected: Selected | None) -> dict[str, tuple[Any, date | None]]:
    """executives: title -> (name, true_from) of that title's selected candidate."""
    members: dict[str, tuple[Any, date | None]] = {}
    if selected is None or selected.value is None:
        return members
    for candidate, _ in selected.ranked:
        members.setdefault(candidate.title, (normalise_value(candidate.value), candidate.true_from))
    return members


def _classify_executives(previous: Selected | None, new: Selected) -> str:
    """Spec 'Changes and corrections' for executives: a title differs when exactly one value has
    a member with it, or both do and the names differ; a differing title is a correction when
    both values have it, both true_from are not null and the new one is on or before the earlier.
    The entry is a correction when every differing title is one."""
    before, after = _members(previous), _members(new)
    differing = [t for t in set(before) | set(after)
                 if (t in before) != (t in after) or (t in before and before[t][0] != after[t][0])]
    for title in differing:
        if title not in before or title not in after:
            return "change"
        (_, earlier), (_, later) = before[title], after[title]
        if earlier is None or later is None or later > earlier:
            return "change"
    return "correction" if differing else "change"


def _investor_times(selected: Selected | None) -> dict[str, date | None]:
    """investors: name -> the earliest non-null true_from among that name's candidates (R4.38)."""
    times: dict[str, date | None] = {}
    if selected is None or selected.value is None:
        return times
    for candidate, _ in selected.ranked:
        name = normalise_value(candidate.value)
        if name not in selected.value:
            continue
        known = [d for d in (candidate.true_from, times.get(name)) if d is not None]
        times[name] = min(known) if known else None
    return times


def _classify_investors(previous: Selected | None, new: Selected) -> str:
    """R4.40: a name in the new value and not in the earlier one counts as a correction when its
    true_from and the earlier value's are both not null and its true_from is on or before the
    earlier value's. The entry is a correction when every name in exactly one value counts as one.
    A name only in the earlier value does not count as a correction (spec silent; see handoff)."""
    before, after = _investor_times(previous), _investor_times(new)
    differing = set(before) ^ set(after)
    if not differing:
        return "change"
    for name in differing:
        if name not in after or name in before:
            return "change"
        earlier = previous.true_from if previous is not None else None
        later = after[name]
        if earlier is None or later is None or later > earlier:
            return "change"
    return "correction"


def classify(previous: Selected | None, new: Selected) -> str:
    """Spec 'Changes and corrections': a correction when both values are not null and the new
    value's true_from is on or before the earlier one's (both non-null); otherwise a change."""
    if new.field == "executives":
        return _classify_executives(previous, new)
    if new.field == "investors":
        return _classify_investors(previous, new)
    if (previous is not None and previous.value is not None and new.value is not None
            and previous.true_from is not None and new.true_from is not None
            and new.true_from <= previous.true_from):
        return "correction"
    return "change"


def build_entries(previous: dict[str, Selected] | None,
                  current: dict[str, Selected], first: bool, *, built_at: datetime) -> list[Entry]:
    """The entries one ready build adds, in FIELDS order. `first` marks the dossier's first ready
    build: each field with a value there gets an `initial` entry and no feed entry. `built_at` is
    the time of this build."""
    entries = []
    for name in SEVEN:
        new = current[name]
        before = previous.get(name) if previous is not None else None
        if first:
            if new.value is not None:
                entries.append(_entry(name, "initial", None, new, built_at))
            continue
        if not differs(before, new):
            continue
        kind = classify(before, new)
        entries.append(_entry(name, kind, before.value if before is not None else None, new,
                              built_at))
    return entries


def _entry(name: str, kind: str, previous: Any, new: Selected, built_at: datetime) -> Entry:
    """A history or feed entry. `learned_at` is the selected value's own time when the value is
    not null; a null value (the field disappeared) takes the build's time, since the build is what
    made it null (ruling on R3.56, R3.62)."""
    has_value = new.value is not None
    return Entry(
        field=name, type=kind, previous=previous, value=new.value,
        true_from=new.true_from if has_value else None,
        learned_at=new.learned_at if has_value else built_at,
        citations=new.citations if has_value else (),
    )


def history(records: list[BuildRecord]) -> dict[str, list[Entry]]:
    """Every field's history, oldest first: the entries of every ready build in order."""
    result: dict[str, list[Entry]] = {name: [] for name in SEVEN}
    previous: dict[str, Selected] | None = None
    for record, current in views(records):
        for entry in build_entries(previous, current, first=previous is None,
                                   built_at=record.time):
            result[entry.field].append(entry)
        previous = current
    return result


def feed_entries(previous: dict[str, Selected] | None, current: dict[str, Selected],
                 first: bool, *, built_at: datetime) -> list[Entry]:
    """The change-feed entries a build adds: its `change` and `correction` entries. Their
    `learned_at` is the time of the build that added them (GET /changes, R3.62), the same as the
    history entry of the same change (see `_entry`)."""
    return [entry for entry in build_entries(previous, current, first, built_at=built_at)
            if entry.type != "initial"]


def unknown_views() -> dict[str, Selected]:
    """Every field unknown: the view of a dossier with no completed ready build."""
    return {name: Selected(field=name, value=None, status="unknown", true_from=None,
                           learned_at=None, citations=(), ranked=())
            for name in SEVEN}


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
