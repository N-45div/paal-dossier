"""Numbers and amounts (Appendix A.4)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

_CLUSTER = re.compile(r"\d+(?:[,.]\d+)*")
_VALID_NUMBER = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_DOLLARS = re.compile(r" (?:US )?dollars", re.IGNORECASE)
_CURRENCY = re.compile(r"US\$|USD|\$", re.IGNORECASE)
_WORD_SCALES = {"thousand": 10**3, "million": 10**6, "billion": 10**9}
_SUFFIX_SCALES = (("mn", 10**6), ("bn", 10**9), ("m", 10**6), ("k", 10**3))


@dataclass(frozen=True)
class Number:
    start: int
    end: int
    text: str

    @property
    def has_decimal(self) -> bool:
        return "." in self.text

    @property
    def value(self) -> Fraction:
        return Fraction(self.text.replace(",", ""))


@dataclass(frozen=True)
class Amount:
    start: int
    end: int
    dollars: Fraction

    @property
    def whole_dollars(self) -> int | None:
        return int(self.dollars) if self.dollars.denominator == 1 else None


def _alnum_at(text: str, i: int) -> bool:
    return 0 <= i < len(text) and text[i].isalnum()


def _clusters(text: str) -> dict[int, Number]:
    """Valid number clusters keyed by start index (letters adjacency not yet checked)."""
    found = {}
    for m in _CLUSTER.finditer(text):
        if _VALID_NUMBER.fullmatch(m.group()):
            found[m.start()] = Number(m.start(), m.end(), m.group())
    return found


def plain_numbers(text: str) -> list[Number]:
    """Numbers not directly next to a letter or digit."""
    return [
        n for n in _clusters(text).values()
        if not _alnum_at(text, n.start - 1) and not _alnum_at(text, n.end)
    ]


def _scaled(text: str, num: Number, *, short_scales: bool) -> list[tuple[int, int]]:
    """Candidate (end, scale) pairs after a number, best first."""
    options: list[tuple[int, int]] = []
    rest = text[num.end:]
    for word, scale in _WORD_SCALES.items():
        if rest[:1] == " " and rest[1:].lower().startswith(word):
            options.append((num.end + 1 + len(word), scale))
    if short_scales:
        for suffix, scale in _SUFFIX_SCALES:
            if rest.lower().startswith(suffix):
                options.append((num.end + len(suffix), scale))
    options.append((num.end, 1))
    return options


def _symbol_amounts(text: str, clusters: dict[int, Number]) -> list[Amount]:
    amounts = []
    for m in _CURRENCY.finditer(text):
        if _alnum_at(text, m.start() - 1):
            continue
        pos = m.end() + (1 if text[m.end():m.end() + 1] == " " else 0)
        num = clusters.get(pos)
        if num is None:
            continue
        for end, scale in _scaled(text, num, short_scales=True):
            if not _alnum_at(text, end):
                amounts.append(Amount(m.start(), end, num.value * scale))
                break
    return amounts


def _dollar_word_amounts(text: str, clusters: dict[int, Number]) -> list[Amount]:
    amounts = []
    for num in clusters.values():
        if _alnum_at(text, num.start - 1):
            continue
        for end, scale in _scaled(text, num, short_scales=False):
            tail = _DOLLARS.match(text, end)
            if tail and not _alnum_at(text, tail.end()):
                amounts.append(Amount(num.start, tail.end(), num.value * scale))
                break
    return amounts


def amounts(text: str) -> list[Amount]:
    clusters = _clusters(text)
    return _symbol_amounts(text, clusters) + _dollar_word_amounts(text, clusters)


def numbers_outside_amounts(text: str) -> list[Number]:
    spans = [(a.start, a.end) for a in amounts(text)]
    return [
        n for n in plain_numbers(text)
        if not any(n.start < e and s < n.end for s, e in spans)
    ]
