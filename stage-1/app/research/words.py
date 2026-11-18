"""Whole-word matching and word classes shared by the support rules."""
from __future__ import annotations

import re
from typing import Iterable

_WS = re.compile(r"\s+")
_NOT_ALNUM_BEFORE = r"(?<![^\W_])"
_NOT_ALNUM_AFTER = r"(?![^\W_])"


def collapse_whitespace(text: str) -> str:
    return _WS.sub(" ", text).strip()


def is_alnum(ch: str) -> bool:
    return ch.isalnum()


def whole_word_pattern(phrases: Iterable[str]) -> re.Pattern:
    """Case-insensitive pattern matching any phrase as whole words, longest first."""
    ordered = sorted(set(phrases), key=len, reverse=True)
    body = "|".join(re.escape(p) for p in ordered)
    return re.compile(
        _NOT_ALNUM_BEFORE + "(?:" + body + ")" + _NOT_ALNUM_AFTER, re.IGNORECASE
    )


def contains_whole_word(text: str, pattern: re.Pattern) -> bool:
    return pattern.search(text) is not None


def alnum_runs(text: str) -> list[tuple[int, int]]:
    """Maximal runs of letters and digits."""
    runs, start = [], None
    for i, ch in enumerate(text):
        if ch.isalnum():
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(text)))
    return runs


def is_capitalised_word(word: str) -> bool:
    return (
        len(word) >= 2
        and word[0].isupper()
        and all(c.isalpha() and c.islower() for c in word[1:])
    )


def is_uppercase_word(word: str) -> bool:
    return len(word) >= 2 and all(c.isalpha() and c.isupper() for c in word)


def capitalised_runs(text: str, joiners: str) -> list[tuple[int, int]]:
    """Maximal runs of capitalised words, each pair joined by one joiner char."""
    runs: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None
    for start, end in alnum_runs(text):
        if not is_capitalised_word(text[start:end]):
            if current:
                runs.append(current)
            current = None
            continue
        if current and start - current[1] == 1 and text[current[1]] in joiners:
            current = (current[0], end)
        else:
            if current:
                runs.append(current)
            current = (start, end)
    if current:
        runs.append(current)
    return runs
