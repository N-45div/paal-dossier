"""Text primitives shared by the support engine: whitespace, whole-word matching, tokens, sentences."""

from __future__ import annotations

import re
from collections.abc import Iterator

_WORD_CHAR = r"[^\W_]"  # a letter or a digit, of any alphabet
_WHITESPACE_RUN = re.compile(r"\s+")
_LINE_BREAK = re.compile(r"\r\n|\n|\r")
_TOKEN = re.compile(r"[^\W_]+")
_SENTENCE_END = re.compile(r"[.!?][\"”’)]*(?=\s)")

# Legal-form suffixes of A.4, matched exactly as written (case-sensitive).
LEGAL_SUFFIXES = (
    "Inc.", "Corp.", "LLC", "LLP", "L.P.", "Ltd", "Limited", "Pty Ltd", "plc", "PLC",
    "GmbH", "AG", "KG", "SE", "AS", "A/S", "ASA", "AB", "Oy", "Oyj", "B.V.", "N.V.",
    "S.A.", "S.A.S.", "S.L.", "S.r.l.", "S.p.A.", "s.r.o.", "a.s.", "K.K.",
)  # fmt: skip
_DOTTED_SUFFIXES = tuple(s for s in LEGAL_SUFFIXES if s.endswith("."))


def collapse_whitespace(text: str) -> str:
    """Write every run of whitespace as one space."""
    return _WHITESPACE_RUN.sub(" ", text)


def is_word_char(char: str) -> bool:
    return char.isalnum()


def whole_word_pattern(phrase: str, *, case_insensitive: bool = True) -> re.Pattern[str]:
    """Pattern matching ``phrase`` with no letter or digit directly before or after it.

    A space in the phrase matches one space.
    """
    body = re.escape(phrase).replace("\\ ", " ")
    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile(rf"(?<!{_WORD_CHAR})(?:{body})(?!{_WORD_CHAR})", flags)


def alternation_pattern(phrases: list[str]) -> re.Pattern[str]:
    """Whole-word, case-insensitive pattern for any phrase; the longest phrase wins at a position."""
    ordered = sorted(phrases, key=len, reverse=True)
    body = "|".join(re.escape(p).replace("\\ ", " ") for p in ordered)
    return re.compile(rf"(?<!{_WORD_CHAR})(?:{body})(?!{_WORD_CHAR})", re.IGNORECASE)


def tokens(text: str) -> Iterator[re.Match[str]]:
    """Maximal runs of letters and digits."""
    return _TOKEN.finditer(text)


def is_capitalised_word(token: str) -> bool:
    return len(token) >= 2 and token[0].isupper() and all(c.islower() for c in token[1:])


def is_uppercase_word(token: str) -> bool:
    return len(token) >= 2 and all(c.isupper() for c in token)


def _ends_legal_suffix_dot(line: str, dot_index: int) -> bool:
    """True when the ``.`` at ``dot_index`` ends a dotted legal-form suffix written as a whole word."""
    head = line[: dot_index + 1]
    for suffix in _DOTTED_SUFFIXES:
        if head.endswith(suffix):
            before = len(head) - len(suffix) - 1
            if before < 0 or not is_word_char(head[before]):
                return True
    return False


def split_line_sentences(line: str) -> list[str]:
    """Split one line into stripped, non-empty sentences (A.1)."""
    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_END.finditer(line):
        if line[match.start()] == "." and _ends_legal_suffix_dot(line, match.start()):
            continue
        sentences.append(line[start : match.end()])
        start = match.end()
    sentences.append(line[start:])
    return [s.strip() for s in sentences if s.strip()]


def split_sentences(prose: str) -> list[str]:
    """Split prose into lines at each line break, and each line into sentences (A.1)."""
    out: list[str] = []
    for line in _LINE_BREAK.split(prose):
        out.extend(split_line_sentences(line))
    return out


def is_single_sentence(excerpt: str) -> bool:
    """An excerpt is a single sentence when, with whitespace runs written as one space, it splits into one."""
    return len(split_line_sentences(collapse_whitespace(excerpt))) == 1
