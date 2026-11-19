"""Evidence for one company and the decision of each field from it (RL1.13, R1.104, R1.57)."""

from __future__ import annotations

import re
from collections import defaultdict

from .pages import collapse_whitespace, prose_of, sentences
from .providers import Claim, Page
from .result import FIELD_NAMES, FieldResult
from .support import FIELDS, supported_values, supports

MAX_EXCERPT_CHARS = 500
MAX_CITATIONS = 3
_HEADCOUNT_RANGES = frozenset(
    ("1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+")
)
_INTEGER_FIELDS = frozenset(("founded_year", "funding_total"))


class Evidence:
    """Every excerpt that supports a value of a field, with the pages it came from."""

    def __init__(self, domain: str) -> None:
        self._domain = domain
        # field -> value -> ordered list of (url, excerpt, provider), without repeats
        self._support: dict[str, dict[object, list[tuple[str, str, str]]]] = {
            name: defaultdict(list) for name in FIELD_NAMES
        }

    def add_page(self, page: Page) -> None:
        """Record what the page's prose supports; header lines are never read (R1.54)."""
        for sentence in sentences(prose_of(page.text)):
            excerpt = collapse_whitespace(sentence)
            if not excerpt or len(excerpt) > MAX_EXCERPT_CHARS:
                continue
            for field, value in supported_values(excerpt, self._domain):
                self._record(field, value, page.url, excerpt, page.provider)

    def add_claim(self, claim: Claim) -> None:
        """Record a research claim, asserted only when its citation supports the value."""
        value = _canonical(claim.field, claim.value)
        excerpt = collapse_whitespace(claim.excerpt or "")
        if value is None or not excerpt or len(excerpt) > MAX_EXCERPT_CHARS:
            return
        if supports(excerpt, self._domain, claim.field, value):
            self._record(claim.field, value, claim.url, excerpt, claim.provider)

    def decide(self) -> dict[str, FieldResult]:
        """Each field holds the value most distinct pages support, else is unknown."""
        return {name: self._decide(name) for name in FIELD_NAMES}

    def _record(self, field: str, value: object, url: str, excerpt: str, provider: str) -> None:
        entries = self._support[field][value]
        if not any(entry[0] == url and entry[1] == excerpt for entry in entries):
            entries.append((url, excerpt, provider))

    def _decide(self, field: str) -> FieldResult:
        candidates = self._support[field]
        if not candidates:
            return FieldResult(None, [])
        best = min(candidates, key=lambda value: _rank(value, candidates[value]))
        return FieldResult(best, _citations(candidates[best]))


def _rank(value: object, entries: list[tuple[str, str, str]]) -> tuple:
    """Most distinct pages first, then the value's ascending form (numbers numerically)."""
    pages = len({url for url, _, _ in entries})
    return (-pages, value if isinstance(value, int) else str(value))


def _citations(entries: list[tuple[str, str, str]]) -> list[dict]:
    """Up to three excerpts, one per distinct page first."""
    first_per_page: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()
    for entry in entries:
        if entry[0] not in seen_urls:
            seen_urls.add(entry[0])
            first_per_page.append(entry)
    rest = [entry for entry in entries if entry not in first_per_page]
    chosen = (first_per_page + rest)[:MAX_CITATIONS]
    return [{"url": url, "excerpt": excerpt, "provider": provider} for url, excerpt, provider in chosen]


def _canonical(field: str, raw: object) -> object | None:
    """The value a claim names, written as Appendix A normalises it; None if malformed."""
    if field not in FIELDS:
        return None
    if field in _INTEGER_FIELDS:
        if isinstance(raw, bool):
            return None
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and re.fullmatch(r"\s*\$?[0-9][0-9,]*\s*", raw):
            return int(raw.strip().lstrip("$").replace(",", ""))
        return None
    if isinstance(raw, str):
        text = collapse_whitespace(raw)
        if field == "headcount_range" and text not in _HEADCOUNT_RANGES:
            return None
        return text or None
    return None
