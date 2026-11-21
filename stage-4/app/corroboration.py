"""`origins`, `corroborated` and `corroborated_since` of a field (stage 4, R4.19-R4.28).

Pure functions of the build records (Rul-S4-2): the same records answer `?as_of=`, `/values`
and imports. Membership comes from the same selected views the history uses (`history.views`):

- a six-field value is one member, keyed by its normalised value;
- an `executives` member is keyed by (title, normalised name);
- an `investors` member is keyed by its normalised name.

A member's standing origins, for a build position `j`, are the origins of every candidate of
that member gathered by ready builds from the build after which it last became a member up to
`j`, inclusive (R4.23, R4.28). A candidate's origin is its stored origin, or the host of its URL
for a candidate imported without one.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.candidates import Candidate, normalise_value
from app.history import views
from app.lineage import host_of
from app.records import BuildRecord


@dataclass(frozen=True)
class Corroboration:
    origins: list[str]
    corroborated: bool
    corroborated_since: datetime | None


NONE = Corroboration(origins=[], corroborated=False, corroborated_since=None)


def origin_of(candidate: Candidate) -> str:
    """The candidate's origin; for one imported without it, the host of its URL (R4.24)."""
    if candidate.origin is not None:
        return candidate.origin
    return host_of(candidate.url) or candidate.url


def _member_keys(field: str, value: Any) -> frozenset:
    if value is None:
        return frozenset()
    if field == "executives":
        return frozenset((member["title"], normalise_value(member["name"])) for member in value)
    if isinstance(value, list):
        return frozenset(normalise_value(name) for name in value)
    return frozenset([normalise_value(value)])


def _candidate_key(field: str, candidate: Candidate) -> Any:
    if field == "executives":
        return (candidate.title, normalise_value(candidate.value))
    return normalise_value(candidate.value)


def corroboration(field: str, records: list[BuildRecord]) -> Corroboration:
    """The three keys of `field` as the build records stand (the last ready build is current)."""
    ready = views(records)
    if not ready:
        return NONE
    members_now = _member_keys(field, ready[-1][1][field].value)
    if not members_now:
        return NONE

    member_sets = [_member_keys(field, selected[field].value) for _, selected in ready]
    # Origins of each candidate key, per ready build position.
    per_position: list[dict[Any, set[str]]] = []
    for record, _ in ready:
        by_key: dict[Any, set[str]] = defaultdict(set)
        for candidate in record.candidates().get(field, []):
            by_key[_candidate_key(field, candidate)].add(origin_of(candidate))
        per_position.append(by_key)

    # The build position after which each current member last became a member.
    start: dict[Any, int] = {}
    for key in members_now:
        position = len(ready) - 1
        while position > 0 and key in member_sets[position - 1]:
            position -= 1
        start[key] = position

    def standing(key: Any, upto: int) -> set[str]:
        found: set[str] = set()
        for position in range(start[key], upto + 1):
            found |= per_position[position].get(key, set())
        return found

    current = per_position[-1]
    origins = sorted({origin for key in members_now for origin in current.get(key, set())})
    corroborated = all(len(current.get(key, set())) >= 2 for key in members_now)

    since = None
    for upto in range(max(start.values()), len(ready)):
        if all(len(standing(key, upto)) >= 2 for key in members_now):
            since = ready[upto][0].time
            break
    return Corroboration(origins=origins, corroborated=corroborated, corroborated_since=since)
