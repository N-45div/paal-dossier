"""Evidence for one build: the candidates each rendered page supports (R2.31-R2.39, RL59-RL64).

Every page is read from its browser text (R2.9). Each (page, value) a page supports for a field
is one candidate, whose excerpt is the smallest verbatim excerpt of that page supporting it. A
research claim adds a candidate only when its citation is verbatim in the rendered text of its
page and supports the claimed value. The decision is made by selection.assemble_field and by
nothing else (RL62).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Optional

from .pages import read_page
from .selection import assemble_field, value_identity
from .support import (
    FIELDS,
    MAX_EXCERPT_CHARS,
    is_verbatim_in_prose,
    normalize_ws,
    page_claims,
    supports,
)


@dataclass
class Page:
    url: str
    kind: str
    published_at: Optional[str]
    provider: str
    prose: str


@dataclass
class Evidence:
    domain: str
    retrieved_at: str
    pages: dict[str, Page] = dataclass_field(default_factory=dict)
    # field -> (url, value identity) -> {"value", "excerpts"}
    claims: dict = dataclass_field(default_factory=dict)

    def add_rendered_page(self, url: str, served_text: str, provider: str = "nimble") -> None:
        """Read a page from its rendered text: its kind, publication time, and every value it supports."""
        if url in self.pages:
            return
        read = read_page(served_text, url, self.domain)
        self.pages[url] = Page(
            url=url, kind=read.kind, published_at=read.published_at, provider=provider, prose=read.prose
        )
        for excerpt, field, value in page_claims(read.prose, self.domain):
            self._claim(field, url, value, excerpt)

    def add_research_claim(self, url: str, field: str, claimed, excerpt: str) -> None:
        """Add the claim as a candidate when its verbatim citation is in the page's rendered text
        and supports the claimed value (RL7, R2.31)."""
        page = self.pages.get(url)
        if field not in FIELDS or page is None:
            return
        excerpt = normalize_ws(excerpt)
        if not (1 <= len(excerpt) <= MAX_EXCERPT_CHARS):
            return
        value = supports(excerpt, self.domain, field)
        claimed_text = _claim_text(field, claimed)
        if value is None or claimed_text is None or str(value) != claimed_text:
            return
        if is_verbatim_in_prose(excerpt, page.prose):
            self._claim(field, url, value, excerpt)

    def _claim(self, field: str, url: str, value, excerpt: str) -> None:
        if not (1 <= len(excerpt) <= MAX_EXCERPT_CHARS):
            return
        entry = self.claims.setdefault(field, {}).setdefault(
            (url, value_identity(value)), {"value": value, "excerpts": set()}
        )
        entry["excerpts"].add(excerpt)

    def candidates(self, field: str) -> list[dict]:
        """One candidate dict per (page, value) for the field (R2.31-R2.36)."""
        out = []
        for (url, _), entry in self.claims.get(field, {}).items():
            page = self.pages[url]
            out.append(
                {
                    "value": entry["value"],
                    "url": url,
                    "excerpt": min(entry["excerpts"]),
                    "provider": page.provider,
                    "kind": page.kind,
                    "published_at": page.published_at,
                }
            )
        return out

    def decide(self) -> dict:
        """Each field as assemble_field returns it: value, status, citations and candidates."""
        return {field: assemble_field(self.candidates(field), self.retrieved_at) for field in FIELDS}


def _claim_text(field: str, claimed) -> Optional[str]:
    """The claimed value in the form supports() returns it, or None when it is not one."""
    if field in ("founded_year", "funding_total"):
        digits = str(claimed).replace(",", "").strip()
        return str(int(digits)) if digits.isdigit() else None
    text = normalize_ws(str(claimed))
    return text or None
