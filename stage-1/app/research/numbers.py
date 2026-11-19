"""Numbers and amounts of Appendix A.4, and their normalisation (A.5)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.research.text import is_word_char

_BLOB = re.compile(r"[0-9]+(?:[.,][0-9]+)*")
_VALID_NUMBER = re.compile(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?")
_CURRENCY_PREFIX = re.compile(r"(?:US\$|USD|\$) ?$", re.IGNORECASE)
_DIRECT_SCALES = (("mn", 10**6), ("m", 10**6), ("k", 10**3), ("bn", 10**9))
_WORD_SCALES = (("thousand", 10**3), ("million", 10**6), ("billion", 10**9))
_DOLLAR_WORDS = ("us dollars", "dollars")

HEADCOUNT_RANGES = (
    (10, "1-10"),
    (50, "11-50"),
    (200, "51-200"),
    (500, "201-500"),
    (1000, "501-1000"),
    (5000, "1001-5000"),
    (10000, "5001-10000"),
)
TOP_HEADCOUNT_RANGE = "10001+"


@dataclass(frozen=True)
class Number:
    start: int
    end: int
    text: str

    @property
    def value(self) -> Decimal:
        return Decimal(self.text.replace(",", ""))

    @property
    def has_decimal_part(self) -> bool:
        return "." in self.text


@dataclass(frozen=True)
class Amount:
    number: Number
    dollars: Decimal  # number times scale

    @property
    def whole_dollars(self) -> int | None:
        """The amount in whole US dollars, or None when it is not a whole number of dollars."""
        if self.dollars != self.dollars.to_integral_value():
            return None
        return int(self.dollars)


def find_numbers(text: str, *, strict: bool = True) -> list[Number]:
    """Numbers per A.4: digits with optional thousands commas and decimal part, not next to a letter.

    With ``strict`` false, a letter next to the digits is allowed (``USD12M``: the prefix and scale of an amount).
    """
    found: list[Number] = []
    for match in _BLOB.finditer(text):
        if not _VALID_NUMBER.fullmatch(match.group()):
            continue
        if strict and match.start() > 0 and text[match.start() - 1].isalpha():
            continue
        if strict and match.end() < len(text) and text[match.end()].isalpha():
            continue
        found.append(Number(match.start(), match.end(), match.group()))
    return found


def _boundary_after(text: str, index: int) -> bool:
    return index >= len(text) or not is_word_char(text[index])


def _starts_with(text: str, index: int, word: str) -> bool:
    return text[index : index + len(word)].lower() == word


def _currency_amount(text: str, number: Number) -> Amount | None:
    prefix = _CURRENCY_PREFIX.search(text, 0, number.start)
    if prefix is None or (prefix.start() > 0 and is_word_char(text[prefix.start() - 1])):
        return None
    for word, scale in _DIRECT_SCALES:
        if _starts_with(text, number.end, word) and _boundary_after(text, number.end + len(word)):
            return Amount(number, number.value * scale)
    for word, scale in _WORD_SCALES:
        if _starts_with(text, number.end, " " + word) and _boundary_after(text, number.end + 1 + len(word)):
            return Amount(number, number.value * scale)
    if _boundary_after(text, number.end):
        return Amount(number, number.value)
    return None


def _dollars_amount(text: str, number: Number) -> Amount | None:
    if number.start > 0 and is_word_char(text[number.start - 1]):
        return None
    scaled = [(f" {w}", s) for w, s in _WORD_SCALES] + [("", 1)]
    for scale_text, scale in scaled:
        if not _starts_with(text, number.end, scale_text):
            continue
        index = number.end + len(scale_text)
        for dollar_word in _DOLLAR_WORDS:
            if _starts_with(text, index, " " + dollar_word) and _boundary_after(text, index + 1 + len(dollar_word)):
                return Amount(number, number.value * scale)
    return None


def find_amounts(text: str) -> list[Amount]:
    """Every amount (A.4) written in ``text``."""
    amounts: list[Amount] = []
    for number in find_numbers(text, strict=False):
        amount = _currency_amount(text, number) or _dollars_amount(text, number)
        if amount is not None:
            amounts.append(amount)
    return amounts


def headcount_range(count: int) -> str:
    """The range of §4 that contains ``count`` (count >= 1)."""
    for upper, label in HEADCOUNT_RANGES:
        if count <= upper:
            return label
    return TOP_HEADCOUNT_RANGE
