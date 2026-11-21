"""The selection rule (stage 2): rank a field's candidates and decide its status and citations.

Pure: no IO and no clock. Ranking, highest first, by authority of the page kind (own and
filing equal and highest, then news, then aggregator; an imported candidate counts as
aggregator), then recency (later publication first; no publication time ranks below every
dated candidate of the same authority), then URL (code point order), then provider
(nimble, tavily, kernel, browserbase), then value (integers numerically, strings by code
point after trimming).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.candidates import PROVIDERS, Candidate, dedupe, normalise_value
from app.clock import parse_rfc3339
from app.support import FIELDS

AUTHORITY: dict[str, int] = {"own": 0, "filing": 0, "news": 1, "aggregator": 2}
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MICRO = timedelta(microseconds=1)


def _instant_micros(published_at: str) -> int:
    """Exact instant of an RFC 3339 timestamp, in microseconds since the epoch."""
    return (parse_rfc3339(published_at).astimezone(timezone.utc) - _EPOCH) // _MICRO


def _value_key(value: Any) -> tuple[int, Any]:
    value = normalise_value(value)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"unsupported candidate value: {value!r}")
    return (0, value) if isinstance(value, int) else (1, value)


def rank_key(candidate: Candidate) -> tuple:
    """Sort key: smaller ranks higher."""
    authority = AUTHORITY[candidate.kind or "aggregator"]
    if candidate.published_at is None:
        recency: tuple[int, int] = (1, 0)
    else:
        recency = (0, -_instant_micros(candidate.published_at))
    provider = PROVIDERS.index(candidate.provider) if candidate.provider in PROVIDERS else len(PROVIDERS)
    return (authority, recency, candidate.url, provider, _value_key(candidate.value))


def rank(candidates: list[Candidate]) -> list[Candidate]:
    """The field's distinct candidates in rank order, the selected one first."""
    return sorted(dedupe(candidates), key=rank_key)


@dataclass(frozen=True)
class Decision:
    """One field's decision: status, selected value, citations and the ranked candidates."""

    status: str  # "known" | "contested" | "unknown"
    ranked: tuple[Candidate, ...]

    @property
    def value(self) -> Any:
        return normalise_value(self.ranked[0].value) if self.ranked else None

    @property
    def citations(self) -> list[dict[str, str]]:
        """url, excerpt and provider of every candidate carrying the selected value, in rank order."""
        return [
            {"url": c.url, "excerpt": c.excerpt, "provider": c.provider}
            for c in self.ranked
            if normalise_value(c.value) == self.value
        ]


def decide_field(candidates: list[Candidate]) -> Decision:
    ranked = tuple(rank(candidates))
    if not ranked:
        return Decision(status="unknown", ranked=())
    distinct = {normalise_value(c.value) for c in ranked}
    return Decision(status="known" if len(distinct) == 1 else "contested", ranked=ranked)


def decide(candidates: dict[str, list[Candidate]]) -> dict[str, Decision]:
    """Decisions for all six fields; a missing field has no candidates."""
    return {name: decide_field(candidates.get(name, [])) for name in FIELDS}
