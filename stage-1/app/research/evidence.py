"""What a build learned: supported sentences from pages and research claims."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .pages import split_page
from .sentences import split_line, split_prose
from .support import Value, supported_values
from .words import collapse_whitespace

MAX_EXCERPT_CHARS = 500
TRUNCATION_MARGIN = 250  # a snippet at least this long may end mid-sentence


@dataclass(frozen=True)
class Candidate:
    field: str
    value: Value
    url: str
    excerpt: str
    provider: str


def _usable(sentence: str) -> str | None:
    text = collapse_whitespace(sentence)
    return text if 1 <= len(text) <= MAX_EXCERPT_CHARS else None


@dataclass
class Evidence:
    domain: str
    candidates: list[Candidate] = field(default_factory=list)
    _full_text_urls: set[str] = field(default_factory=set)
    _snippets: dict[str, tuple[str, str]] = field(default_factory=dict)

    def add_page(self, url: str, served_text: str, provider: str) -> None:
        """Every supporting sentence of a page's prose."""
        self._full_text_urls.add(url)
        for sentence in split_prose(split_page(served_text)[1]):
            self._add_sentence(url, sentence, provider)

    def add_snippet(self, url: str, snippet: str, provider: str) -> None:
        """A search snippet: used only for a page whose full text never arrived."""
        self._snippets.setdefault(url, (snippet, provider))

    def add_claims(self, structured: Any, citations: list[Any]) -> None:
        """Research claims: a citation counts when its text supports the claimed value."""
        claims = structured if isinstance(structured, dict) else {}
        for citation in citations:
            name = (citation.field or "").removeprefix("$.")
            claimed = claims.get(name)
            if claimed is None or not citation.snippet or not citation.url:
                continue
            for sentence in split_line(collapse_whitespace(citation.snippet)):
                self._add_sentence(citation.url, sentence, "nimble", only=(name, claimed))

    def finish(self) -> list[Candidate]:
        """Candidates, with snippet sentences for pages that have no full text."""
        for url, (snippet, provider) in self._snippets.items():
            if url in self._full_text_urls:
                continue
            sentences = split_prose(snippet)
            if len(snippet) >= TRUNCATION_MARGIN and sentences:
                sentences = sentences[:-1]
            for sentence in sentences:
                self._add_sentence(url, sentence, provider)
        return sorted(set(self.candidates), key=lambda c: (c.url, c.excerpt, c.field))

    def _add_sentence(self, url: str, sentence: str, provider: str, only: tuple[str, Any] | None = None) -> None:
        excerpt = _usable(sentence)
        if excerpt is None:
            return
        for name, value in supported_values(excerpt, self.domain).items():
            if only is None or (name == only[0] and str(value) == str(only[1])):
                self.candidates.append(Candidate(name, value, url, excerpt, provider))
