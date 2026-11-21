"""Independent selection-rule oracle for stage 2 (spec: "The selection rule", "Status", Rul-S2-8).

Written by the Prover from the spec text only.

Rank a field's candidates, highest first, by:
1. authority of kind: own and filing equal and highest, then news, then aggregator;
2. recency within the same authority: later published_at ranks higher; undated ranks below dated;
3. url: smaller by Unicode code point ranks higher; then provider nimble, tavily, kernel, browserbase;
4. value: smaller ranks higher (numbers numerically, strings by code point after strip).
An imported candidate (kind None) has the authority of aggregator.
"""
from __future__ import annotations

from datetime import datetime

AUTHORITY = {"own": 0, "filing": 0, "news": 1, "aggregator": 2}
PROVIDER_ORDER = {"nimble": 0, "tavily": 1, "kernel": 2, "browserbase": 3}


def _instant(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _value_key(v):
    return v.strip() if isinstance(v, str) else v


def rank_key(c: dict):
    authority = AUTHORITY[c["kind"]] if c.get("kind") else AUTHORITY["aggregator"]
    if c.get("published_at") is None:
        recency = (1, 0.0)
    else:
        recency = (0, -_instant(c["published_at"]))
    return (authority, recency, c["url"], PROVIDER_ORDER[c["provider"]], _value_key(c["value"]))


def ranked(cands: list[dict]) -> list[dict]:
    return sorted(cands, key=rank_key)


def expected_status(cands: list[dict]) -> str:
    if not cands:
        return "unknown"
    values = {_value_key(c["value"]) for c in cands}
    return "known" if len(values) == 1 else "contested"


def expected_citations(ranked_cands: list[dict]) -> list[dict]:
    """Every candidate with the selected value, in rank order: url, excerpt, provider only."""
    if not ranked_cands:
        return []
    chosen = _value_key(ranked_cands[0]["value"])
    return [{"url": c["url"], "excerpt": c["excerpt"], "provider": c["provider"]}
            for c in ranked_cands if _value_key(c["value"]) == chosen]
