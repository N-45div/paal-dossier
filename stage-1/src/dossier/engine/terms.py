"""Vocabulary and character classes of Appendix A (phrases, suffixes, value formats).

Every pattern here is a fragment of a regular expression. Letters are classified with the
Unicode case properties of Python's ``str``, so ``Zürich`` and ``Müller`` are capitalised
words, and "letter or digit" means the ``[^\\W_]`` class.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable


def _char_class(predicate: Callable[[str], bool]) -> str:
    """Regex character class holding every code point that satisfies ``predicate``."""
    ranges: list[tuple[int, int]] = []
    start = -1
    last = -1
    for code_point in range(0x110000):
        if predicate(chr(code_point)):
            if start < 0:
                start = code_point
            last = code_point
        elif start >= 0:
            ranges.append((start, last))
            start = -1
    if start >= 0:
        ranges.append((start, last))
    body = "".join(
        f"\\U{low:08x}" if low == high else f"\\U{low:08x}-\\U{high:08x}"
        for low, high in ranges
    )
    return f"[{body}]"


UPPER = _char_class(str.isupper)
LOWER = _char_class(str.islower)

BEFORE_WORD = r"(?<![^\W_])"
AFTER_WORD = r"(?![^\W_])"

# A capitalised word: an uppercase letter then lowercase letters, as a whole word (A.4).
CAP_WORD = rf"{BEFORE_WORD}{UPPER}{LOWER}+{AFTER_WORD}"
# An uppercase word: two or more uppercase letters, as a whole word (A.4).
UPPER_WORD = rf"{BEFORE_WORD}{UPPER}{{2,}}{AFTER_WORD}"

# A number (A.4): digits with optional comma groups of three and an optional decimal part.
NUMBER = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?"
# Digits joined to other digits by ',' or '.' are not a number, so a number neither starts
# nor ends inside such a run.
NUMBER_BEFORE = r"(?<![^\W_])(?<![0-9][.,])"
NUMBER_AFTER = r"(?![^\W_]|[.,][0-9])"

# Legal-form suffixes, matched exactly as written (A.4).
LEGAL_SUFFIXES: tuple[str, ...] = (
    "Inc.",
    "Corp.",
    "LLC",
    "LLP",
    "L.P.",
    "Ltd",
    "Limited",
    "Pty Ltd",
    "plc",
    "PLC",
    "GmbH",
    "AG",
    "KG",
    "SE",
    "AS",
    "A/S",
    "ASA",
    "AB",
    "Oy",
    "Oyj",
    "B.V.",
    "N.V.",
    "S.A.",
    "S.A.S.",
    "S.L.",
    "S.r.l.",
    "S.p.A.",
    "s.r.o.",
    "a.s.",
    "K.K.",
)
# Suffixes whose final '.' does not end a sentence (A.1).
DOT_SUFFIXES: tuple[str, ...] = tuple(s for s in LEGAL_SUFFIXES if s.endswith("."))

STATEMENT_PHRASES: dict[str, tuple[str, ...]] = {
    "legal_name": (
        "legal name",
        "registered name",
        "registered as",
        "registered company",
        "legal entity",
        "name of record",
    ),
    "hq_city": (
        "headquartered in",
        "headquarters in",
        "head office in",
        "based in",
        "registered office in",
        "registered seat in",
    ),
    "ceo": ("chief executive officer", "chief executive", "CEO"),
    "founded_year": ("founded", "founding", "established", "incorporated"),
    "headcount_range": (
        "employs",
        "employees",
        "staff",
        "people",
        "headcount",
        "workforce",
    ),
    "funding_total": ("raised", "funding", "invested", "investment"),
}

NEGATING_PHRASES: tuple[str, ...] = (
    "in talks to",
    "plans to",
    "planning to",
    "wants to",
    "expects to",
    "hopes to",
    "aims to",
    "seeking",
    "could",
    "would",
    "might",
    "reportedly",
    "rumoured",
    "former",
    "formerly",
    "will become",
    "not",
)

# Scale words and abbreviations of amounts (A.4, A.5), keyed in lower case.
SCALE_FACTORS: dict[str, int] = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "mn": 1_000_000,
    "million": 1_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
}


def phrase_alternation(phrases: Iterable[str]) -> str:
    """Case-insensitive alternation of literal phrases, longest first."""
    ordered = sorted(phrases, key=len, reverse=True)
    return "(?i:" + "|".join(re.escape(phrase) for phrase in ordered) + ")"


def whole_phrases(phrases: Iterable[str]) -> re.Pattern[str]:
    """Pattern matching any of ``phrases`` as a whole word, case-insensitively."""
    return re.compile(BEFORE_WORD + phrase_alternation(phrases) + AFTER_WORD)


def suffix_alternation() -> str:
    """Case-sensitive alternation of the legal-form suffixes, longest first."""
    ordered = sorted(LEGAL_SUFFIXES, key=len, reverse=True)
    return "(?:" + "|".join(re.escape(suffix) for suffix in ordered) + ")"
