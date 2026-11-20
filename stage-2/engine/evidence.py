"""Evidence store and the decision per field (RL7, RL29).

Candidates come from the sentences of every gathered text and from research claims whose
verbatim citation supports the claimed value. A gathered text is kept per (url, provider):
two providers serving one URL give two texts, and each supplies its own sentences (RL29).
A field holds the value with the most distinct supporting pages; ties go to a value a company
page supports, then to the lexicographically smallest value. Its citations are 1-3 excerpts
from distinct pages, each labelled with the provider whose text holds the excerpt; when both
providers hold it, nimble is preferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Optional

from .discovery import is_company_host
from .support import (
    FIELDS,
    MAX_EXCERPT_CHARS,
    is_verbatim_in_prose,
    normalize_ws,
    page_claims,
    parse_page,
    supports,
)

MAX_CITATIONS = 3
PROVIDER_PREFERENCE = ("nimble", "tavily")  # when both served an excerpt, nimble is labelled


@dataclass
class Page:
    url: str
    prose: str
    provider: str


@dataclass
class Evidence:
    domain: str
    # (url, provider) -> the text that provider served for the URL, as its prose
    pages: dict[tuple[str, str], Page] = dataclass_field(default_factory=dict)
    # field -> value -> (url, provider) -> {excerpt, ...}
    support: dict = dataclass_field(default_factory=dict)

    def add_served_text(self, url: str, served_text: str, provider: str, searched: bool = True) -> None:
        """Gather a page from its served text: header lines, a blank line, then the prose."""
        _, prose = parse_page(served_text)
        self.add_prose(url, prose, provider, searched=searched)

    def add_prose(self, url: str, prose: str, provider: str, searched: bool = True) -> None:
        """Gather one provider's text for a URL. The first text gathered for that (url, provider)
        is kept.

        RL21: a page that no search of the build returned (searched=False) is kept only for
        verifying research claims. Its sentences do not become evidence for any field.
        """
        key = (url, provider)
        if key in self.pages:
            return
        self.pages[key] = Page(url=url, prose=prose, provider=provider)
        if not searched:
            return
        for excerpt, field, value in page_claims(prose, self.domain):
            self._add(field, value, key, excerpt)

    def add_research_claim(self, url: str, field: str, claimed, excerpt: str) -> None:
        """Assert a research claim for each gathered text of the URL that holds its verbatim
        citation and supports the claimed value."""
        if field not in FIELDS:
            return
        excerpt = normalize_ws(excerpt)
        if not (1 <= len(excerpt) <= MAX_EXCERPT_CHARS):
            return
        value = supports(excerpt, self.domain, field)
        claimed_text = _claim_text(field, claimed)
        if value is None or claimed_text is None or str(value) != claimed_text:
            return
        for key in self._keys_for(url):
            if is_verbatim_in_prose(excerpt, self.pages[key].prose):
                self._add(field, value, key, excerpt)

    def _keys_for(self, url: str) -> list[tuple[str, str]]:
        """The (url, provider) keys held for a URL, in provider preference order."""
        held = [key for key in self.pages if key[0] == url]
        return sorted(held, key=lambda key: _preference(key[1]))

    def _add(self, field: str, value, key: tuple[str, str], excerpt: str) -> None:
        if not (1 <= len(excerpt) <= MAX_EXCERPT_CHARS):
            return
        by_value = self.support.setdefault(field, {})
        by_source = by_value.setdefault(value, {})
        by_source.setdefault(key, set()).add(excerpt)

    def decide(self) -> dict:
        """The six fields, each {"value", "citations"}; unknown fields have value None."""
        return {field: self._decide_field(field) for field in FIELDS}

    def _decide_field(self, field: str) -> dict:
        by_value = self.support.get(field)
        if not by_value:
            return {"value": None, "citations": []}
        best = min(by_value, key=lambda value: self._rank_key(value, by_value[value]))
        return {"value": best, "citations": self._citations(best, by_value[best])}

    def _rank_key(self, value, by_source: dict):
        """Most distinct pages first, then a company page, then the smallest value."""
        urls = {url for url, _ in by_source}
        company_page = any(is_company_host(url, self.domain) for url in urls)
        return (-len(urls), not company_page, str(value))

    def _citations(self, value, by_source: dict) -> list[dict]:
        """One citation per distinct URL, from the most preferred provider that holds an excerpt
        for the value at that URL."""
        chosen: dict[str, tuple[str, str]] = {}
        for key in sorted(by_source, key=lambda key: _preference(key[1])):
            chosen.setdefault(key[0], key)
        urls = sorted(chosen, key=lambda url: (not is_company_host(url, self.domain), url))
        citations = []
        for url in urls[:MAX_CITATIONS]:
            key = chosen[url]
            citations.append(
                {"url": url, "excerpt": min(by_source[key]), "provider": self.pages[key].provider}
            )
        return citations


def _preference(provider: str) -> int:
    return PROVIDER_PREFERENCE.index(provider) if provider in PROVIDER_PREFERENCE else len(PROVIDER_PREFERENCE)


def _claim_text(field: str, claimed) -> Optional[str]:
    """The claimed value in the form supports() returns it, or None when it is not one."""
    if field in ("founded_year", "funding_total"):
        digits = str(claimed).replace(",", "").strip()
        return str(int(digits)) if digits.isdigit() else None
    text = normalize_ws(str(claimed))
    return text or None
