"""Whole-word, case-insensitive matching and word scanning used by Appendix A."""

import re
from collections.abc import Iterable

# A word: a maximal run of letters, not adjacent to any other letter or digit.
WORD = re.compile(r"(?<![^\W_])[^\W\d_]+(?![^\W_])")


def whole_words(alternatives: Iterable[str]) -> re.Pattern[str]:
    """Pattern matching any alternative as whole words, case-insensitively.

    An alternative containing spaces matches exactly one space at each gap.
    Longer alternatives are tried first so that the longest match wins.
    """
    ordered = sorted(set(alternatives), key=len, reverse=True)
    body = "|".join(" ".join(re.escape(word) for word in alt.split(" ")) for alt in ordered)
    return re.compile(rf"(?<![^\W_])(?:{body})(?![^\W_])", re.IGNORECASE)


def is_capitalised(word: str) -> bool:
    """An uppercase letter followed by one or more lowercase letters."""
    return len(word) >= 2 and word[0].isupper() and word[1:].islower()


def is_uppercase_word(word: str) -> bool:
    """Two or more uppercase letters."""
    return len(word) >= 2 and word.isupper()


def word_at(text: str, pos: int) -> re.Match[str] | None:
    """The whole word starting exactly at pos, or None."""
    return WORD.match(text, pos)
