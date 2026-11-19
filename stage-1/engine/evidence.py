"""Evidence store and the decision per field (RL7).

Candidates come from the sentences of every gathered page (support.page_claims) and from
research claims whose verbatim citation supports the claimed value. A field holds the value
with the most distinct supporting pages; ties go to a value a company page supports, then
to the lexicographically smallest value. Its citations are 1-3 excerpts from distinct pages.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Optional

from .discovery import is_company_host
from .support import (
    FIELDS,
    is_verbatim_in_prose,
    normalize_ws,
    page_claims,
    parse_page,
    supports,
)

MAX_EXCERPT_CHARS = 500
MAX_CITATIONS = 3


@dataclass
class Page:
    url: str
    prose: str
    provider: str


@dataclass
class Evidence:
    domain: str
    pages: dict[str, Page] = dataclass_field(default_factory=dict)
    # field -> value -> url -> {excerpt, ...}
    support: dict = dataclass_field(default_factory=dict)

    def add_page(self, url: str, served_text: str, provider: str) -> None:
        """Gather a page's text. The first text served for a URL is kept."""
        if url in self.pages:
            return
        _, prose = parse_page(served_text)
        self.pages[url] = Page(url=url, prose=prose, provider=provider)
        for sentence, field, value in page_claims(prose, self.domain):
            self._add(field, value, url, sentence)

    def add_research_claim(self, url: str, field: str, claimed, excerpt: str) -> None:
        """Assert a research claim only when its verbatim citation supports the claimed value."""
        page = self.pages.get(url)
        if field not in FIELDS or page is None:
            return
        excerpt = normalize_ws(excerpt)
        if not (1 <= len(excerpt) <= MAX_EXCERPT_CHARS):
            return
        if not is_verbatim_in_prose(excerpt, page.prose):
            return
        value = supports(excerpt, self.domain, field)
        claimed_text = _claim_text(field, claimed)
        if value is None or claimed_text is None or str(value) != claimed_text:
            return
        self._add(field, value, url, excerpt)

    def _add(self, field: str, value, url: str, excerpt: str) -> None:
        if not (1 <= len(excerpt) <= MAX_EXCERPT_CHARS):
            return
        by_value = self.support.setdefault(field, {})
        by_url = by_value.setdefault(value, {})
        by_url.setdefault(url, set()).add(excerpt)

    def decide(self) -> dict:
        """The six fields, each {"value", "citations"}; unknown fields have value None."""
        return {field: self._decide_field(field) for field in FIELDS}

    def _decide_field(self, field: str) -> dict:
        by_value = self.support.get(field)
        if not by_value:
            return {"value": None, "citations": []}
        best = min(by_value, key=lambda value: self._rank_key(value, by_value[value]))
        return {"value": best, "citations": self._citations(best, by_value[best])}

    def _rank_key(self, value, by_url: dict):
        """Most distinct pages first, then a company page, then the smallest value."""
        company_page = any(is_company_host(url, self.domain) for url in by_url)
        return (-len(by_url), not company_page, str(value))

    def _citations(self, value, by_url: dict) -> list[dict]:
        urls = sorted(by_url, key=lambda url: (not is_company_host(url, self.domain), url))
        citations = []
        for url in urls[:MAX_CITATIONS]:
            page = self.pages[url]
            citations.append(
                {"url": url, "excerpt": min(by_url[url]), "provider": page.provider}
            )
        return citations


def _claim_text(field: str, claimed) -> Optional[str]:
    """The claimed value in the form supports() returns it, or None when it is not one."""
    if field in ("founded_year", "funding_total"):
        digits = str(claimed).replace(",", "").strip()
        return str(int(digits)) if digits.isdigit() else None
    text = normalize_ws(str(claimed))
    return text or None
