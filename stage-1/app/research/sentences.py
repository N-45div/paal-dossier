"""Sentence splitting (Appendix A.1)."""
from __future__ import annotations

import re

from .pages import split_lines
from .words import collapse_whitespace

LEGAL_FORM_SUFFIXES = (
    "Inc.", "Corp.", "LLC", "LLP", "L.P.", "Ltd", "Limited", "Pty Ltd", "plc",
    "PLC", "GmbH", "AG", "KG", "SE", "AS", "A/S", "ASA", "AB", "Oy", "Oyj",
    "B.V.", "N.V.", "S.A.", "S.A.S.", "S.L.", "S.r.l.", "S.p.A.", "s.r.o.",
    "a.s.", "K.K.",
)
_DOTTED_SUFFIXES = tuple(s for s in LEGAL_FORM_SUFFIXES if s.endswith("."))
_TERMINATOR = re.compile(r"[.!?][\"”’)]*(?=\s)")


def _ends_dotted_suffix(text: str, dot_index: int) -> bool:
    """True when the '.' at dot_index ends a legal-form suffix written as a whole word."""
    upto = text[: dot_index + 1]
    for suffix in _DOTTED_SUFFIXES:
        if upto.endswith(suffix):
            before = len(upto) - len(suffix) - 1
            if before < 0 or not upto[before].isalnum():
                return True
    return False


def split_line(line: str) -> list[str]:
    sentences, start = [], 0
    for m in _TERMINATOR.finditer(line):
        if line[m.start()] == "." and _ends_dotted_suffix(line, m.start()):
            continue
        sentences.append(line[start:m.end()])
        start = m.end()
    sentences.append(line[start:])
    return [s.strip() for s in sentences if s.strip()]


def split_prose(prose: str) -> list[str]:
    """Sentences of a page's prose: split at line breaks, then at sentence ends."""
    out: list[str] = []
    for line in split_lines(prose):
        out.extend(split_line(line))
    return out


def is_single_sentence(excerpt: str) -> bool:
    return len(split_line(collapse_whitespace(excerpt))) == 1
