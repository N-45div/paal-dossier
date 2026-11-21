"""The change feed (stage 3, Rul-S3-4): append-only entries, each with a `seq` assigned in the
same synchronous step that appends the build's entries, so no seq repeats or is skipped, and
the counter continues from the largest persisted seq after a restart."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.history import Entry


@dataclass(frozen=True)
class FeedRow:
    seq: int
    domain: str
    field: str
    type: str  # "change" | "correction"
    previous: Any
    value: Any
    true_from: date | None
    learned_at: datetime | None


def append_build(feed: list[FeedRow], next_seq: int, domain: str,
                 entries: list[Entry]) -> int:
    """Append one build's feed entries; returns the next free seq."""
    seq = next_seq
    for entry in entries:
        feed.append(FeedRow(seq=seq, domain=domain, field=entry.field, type=entry.type,
                            previous=entry.previous, value=entry.value,
                            true_from=entry.true_from, learned_at=entry.learned_at))
        seq += 1
    return seq
