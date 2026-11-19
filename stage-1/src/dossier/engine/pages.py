"""Page text: header and prose (R1.58), and the split of prose into sentences (A.1)."""

from __future__ import annotations

import re

from .terms import CAP_WORD, DOT_SUFFIXES

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_WHITESPACE = re.compile(r"\s+")
# A header line starts with a capitalised word, or several joined by '-', then ':'.
_HEADER_LINE = re.compile(rf"{CAP_WORD}(?:-{CAP_WORD})*:")
# A sentence ends after '.', '!' or '?', with any closing quote or bracket directly after,
# when whitespace follows.
_SENTENCE_END = re.compile(r"[.!?][\"”’)]*(?=\s)")


def collapse_whitespace(text: str) -> str:
    """Every run of whitespace written as one space, without surrounding whitespace."""
    return _WHITESPACE.sub(" ", text).strip()


def prose_of(text: str) -> str:
    """The prose of a served page text.

    A text whose first line is a header line starts with a header that ends at the first
    empty line; the prose is everything after that line. Any other text is all prose.
    """
    lines = _LINE_BREAK.split(text)
    if not _HEADER_LINE.match(lines[0]):
        return text
    for index, line in enumerate(lines):
        if not line.strip():
            return "\n".join(lines[index + 1 :])
    return ""


def sentences(prose: str) -> list[str]:
    """Split prose into lines, then each line into sentences (A.1)."""
    found: list[str] = []
    for line in _LINE_BREAK.split(prose):
        found.extend(_split_line(line))
    return found


def _split_line(line: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    for match in _SENTENCE_END.finditer(line):
        if match.group(0).startswith(".") and _ends_legal_suffix(line, match.start()):
            continue
        pieces.append(line[start : match.end()])
        start = match.end()
    pieces.append(line[start:])
    return [piece.strip() for piece in pieces if piece.strip()]


def _ends_legal_suffix(line: str, dot: int) -> bool:
    """Whether the '.' at ``dot`` ends a legal-form suffix written as a whole word."""
    for suffix in DOT_SUFFIXES:
        start = dot + 1 - len(suffix)
        if start < 0 or line[start : dot + 1] != suffix:
            continue
        if start == 0 or not line[start - 1].isalnum():
            return True
    return False
