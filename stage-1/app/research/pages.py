"""Served page text: header lines, prose, facts, and whether an excerpt is a citation of it."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.research.text import collapse_whitespace, is_capitalised_word, split_sentences

_HEADER_LINE = re.compile(r"^([^\W\d_]+(?:-[^\W\d_]+)*): ?(.*)$")
_LINE_BREAK = re.compile(r"\r\n|\n|\r")
MAX_EXCERPT_LENGTH = 500


@dataclass(frozen=True)
class ParsedPage:
    headers: tuple[tuple[str, str], ...]
    prose: str

    @property
    def facts(self) -> dict:
        """The JSON object of the ``Facts:`` header, or {} when absent or unparseable. Informative only."""
        for name, value in self.headers:
            if name == "Facts":
                try:
                    parsed = json.loads(value)
                except ValueError:
                    return {}
                return parsed if isinstance(parsed, dict) else {}
        return {}


@dataclass
class ServedText:
    """Text a provider served for the page at ``url``; ``complete`` is false for a truncated body or snippet."""

    url: str
    provider: str
    text: str
    complete: bool = True
    title: str = ""
    parsed: ParsedPage = field(init=False)

    def __post_init__(self) -> None:
        self.parsed = parse_page(self.text)


def is_header_line(line: str) -> bool:
    match = _HEADER_LINE.match(line)
    return bool(match) and all(is_capitalised_word(w) for w in match.group(1).split("-"))


def parse_page(text: str) -> ParsedPage:
    """Split a page text into header lines and prose (§4 Pages)."""
    lines = _LINE_BREAK.split(text)
    if not lines or not is_header_line(lines[0]):
        return ParsedPage((), text)
    headers: list[tuple[str, str]] = []
    prose_start = len(lines)
    for index, line in enumerate(lines):
        if line == "":
            prose_start = index + 1
            break
        match = _HEADER_LINE.match(line)
        if match and is_header_line(line):
            headers.append((match.group(1), match.group(2)))
    prose_lines = lines[prose_start:]
    return ParsedPage(tuple(headers), "\n".join(prose_lines))


def prose_sentences(served: ServedText) -> list[str]:
    """Whole sentences of the prose; the trailing fragment of a truncated text is dropped."""
    prose = served.parsed.prose
    sentences = split_sentences(prose)
    if sentences and not served.complete and not prose.rstrip().endswith((".", "!", "?", '"', "”", "’", ")")):
        sentences = sentences[:-1]
    return [s for s in (collapse_whitespace(s) for s in sentences) if 1 <= len(s) <= MAX_EXCERPT_LENGTH]


def is_citation_of(excerpt: str, served: ServedText) -> bool:
    """True when the excerpt is copied from the served page's prose, whitespace runs written as one space."""
    if not 1 <= len(excerpt) <= MAX_EXCERPT_LENGTH:
        return False
    return excerpt in collapse_whitespace(served.parsed.prose)
