"""Candidates (stage 2, Rul-S2-1): one value of one field, supported by one excerpt of one page.

A candidate's ``value`` is the normalised value (str or int). ``kind`` is the page kind
(``own``, ``filing``, ``news``, ``aggregator``), or None for a candidate imported from a
stage-1 export. ``published_at`` is an RFC 3339 string with an explicit offset, or None.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

KINDS: tuple[str, ...] = ("own", "filing", "news", "aggregator")
PROVIDERS: tuple[str, ...] = ("nimble", "tavily", "kernel", "browserbase")


@dataclass(frozen=True)
class Candidate:
    """One candidate. Stage 3 (Rul-S3-1): ``title`` is set only for an `executives` candidate
    (``value`` is then the person's name); ``true_from`` is copied from the candidate's page
    version; ``learned_at`` is filled by the history fold, not by the research engine."""

    value: Any
    url: str
    excerpt: str
    provider: str
    kind: str | None = None
    published_at: str | None = None
    title: str | None = None
    true_from: date | None = None
    learned_at: datetime | None = None
    # The field this candidate is for (stage 3): needed where candidates of several fields
    # sit in one page version. None for stage-2 callers, which key candidates by field.
    field: str | None = None


def normalise_value(value: Any) -> Any:
    """Surrounding whitespace is removed from strings; other values are kept as they are."""
    return value.strip() if isinstance(value, str) else value


def identity(candidate: Candidate) -> tuple[Any, str]:
    """Rul-S2-8: a candidate is identified by its value and its page (url). A page gives at
    most one candidate per value; the excerpt and provider of the first one are kept."""
    return (normalise_value(candidate.value), candidate.url)


def dedupe(candidates: list[Candidate]) -> list[Candidate]:
    """Keep the first candidate of each (value, url), in the given order."""
    seen: set[tuple[Any, str]] = set()
    unique: list[Candidate] = []
    for candidate in candidates:
        key = identity(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def from_citation(value: Any, citation: dict[str, str]) -> Candidate:
    """An imported candidate (Rul-S2-2): kind and publication time are unknown."""
    return Candidate(
        value=value,
        url=citation["url"],
        excerpt=citation["excerpt"],
        provider=citation["provider"],
        kind=None,
        published_at=None,
    )
