"""Appendix A of the Dossier stage 1 specification: when an excerpt supports a value.

Pure, dependency-free functions. The service decides support by these rules alone.
Text handling: whitespace runs are collapsed to one space before any matching, so a
statement phrase or name with a space matches exactly one space in the text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Optional

FIELDS = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)

HEADCOUNT_RANGES = (
    (10, "1-10"),
    (50, "11-50"),
    (200, "51-200"),
    (500, "201-500"),
    (1000, "501-1000"),
    (5000, "1001-5000"),
    (10000, "5001-10000"),
)
HEADCOUNT_TOP = "10001+"

STATEMENT_PHRASES = {
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

NEGATING_PHRASES = (
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

LEGAL_SUFFIXES = (
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
# Longest first so that the longest suffix at a position is tried first.
_SUFFIXES_LONGEST_FIRST = tuple(sorted(LEGAL_SUFFIXES, key=len, reverse=True))
_DOTTED_SUFFIXES = tuple(s for s in LEGAL_SUFFIXES if s.endswith("."))

_SENTENCE_CLOSERS = '"”’)'
_SCALE_VALUES = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "mn": 1_000_000,
    "million": 1_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
}

# ---------------------------------------------------------------- text basics


def normalize_ws(text: str) -> str:
    """Collapse every run of whitespace to one space and strip the ends."""
    return " ".join(text.split())


def _is_alnum_at(text: str, index: int) -> bool:
    return 0 <= index < len(text) and text[index].isalnum()


def _ends_with_legal_suffix(line: str, dot_index: int) -> bool:
    """True when the '.' at dot_index ends a legal-form suffix written as a whole word."""
    end = dot_index + 1
    for suffix in _DOTTED_SUFFIXES:
        start = end - len(suffix)
        if start >= 0 and line[start:end] == suffix and not _is_alnum_at(line, start - 1):
            return True
    return False


def split_sentences(line: str) -> list[str]:
    """Split one line of prose into sentences (A.1). Empty sentences are dropped."""
    pieces: list[str] = []
    start = 0
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch in ".!?":
            j = i + 1
            while j < n and line[j] in _SENTENCE_CLOSERS:
                j += 1
            ends_here = j < n and line[j].isspace()
            if ends_here and not (ch == "." and _ends_with_legal_suffix(line, i)):
                pieces.append(line[start:j])
                start = j
                i = j
                continue
        i += 1
    pieces.append(line[start:])
    sentences = (normalize_ws(piece) for piece in pieces)
    return [sentence for sentence in sentences if sentence]


def is_single_sentence(excerpt: str) -> bool:
    """A.1: with whitespace runs written as one space, the excerpt is exactly one sentence."""
    return len(split_sentences(normalize_ws(excerpt))) == 1


def is_verbatim_in_prose(excerpt: str, prose: str) -> bool:
    """True when excerpt is a whitespace-normalised substring of the served prose."""
    needle = normalize_ws(excerpt)
    return bool(needle) and needle in normalize_ws(prose)


# ------------------------------------------------------------- phrase matching


@lru_cache(maxsize=None)
def _phrase_pattern(phrase: str) -> re.Pattern:
    body = " ".join(re.escape(word) for word in phrase.split(" "))
    return re.compile(r"(?<![^\W_])" + body + r"(?![^\W_])", re.IGNORECASE)


def find_phrase(sentence: str, phrase: str) -> list[re.Match]:
    """Whole-word, case-insensitive matches of phrase in sentence."""
    return list(_phrase_pattern(phrase).finditer(sentence))


def _has_any_phrase(sentence: str, phrases) -> bool:
    return any(find_phrase(sentence, phrase) for phrase in phrases)


def company_name(domain: str) -> str:
    """A.2: the first label of the domain with each '-' read as a space."""
    return domain.split(".")[0].replace("-", " ")


def company_mentions(domain: str) -> tuple[str, ...]:
    """The domain and the company name, either of which names the company (A.2)."""
    return (domain, company_name(domain))


def names_company(sentence: str, domain: str) -> bool:
    return any(find_phrase(sentence, mention) for mention in company_mentions(domain))


# --------------------------------------------------------------- word shapes


def _capitalised_word_end(text: str, start: int) -> Optional[int]:
    """End index of a capitalised word (uppercase, then lowercase) starting at start."""
    n = len(text)
    if start >= n or not text[start].isupper() or _is_alnum_at(text, start - 1):
        return None
    end = start + 1
    while end < n and text[end].islower():
        end += 1
    if end == start + 1 or _is_alnum_at(text, end):
        return None
    return end


def _uppercase_word_end(text: str, start: int) -> Optional[int]:
    """End index of an uppercase word (two or more uppercase letters) starting at start."""
    n = len(text)
    if start >= n or _is_alnum_at(text, start - 1):
        return None
    end = start
    while end < n and text[end].isupper():
        end += 1
    if end - start < 2 or _is_alnum_at(text, end):
        return None
    return end


def _suffix_end(text: str, start: int) -> Optional[int]:
    """End index of a legal-form suffix starting at start, with no letter/digit after it."""
    for suffix in _SUFFIXES_LONGEST_FIRST:
        if text.startswith(suffix, start):
            end = start + len(suffix)
            if not _is_alnum_at(text, end):
                return end
    return None


# ------------------------------------------------------------------- numbers

_NUMBER_TOKEN = re.compile(r"[0-9][0-9,.]*[0-9]|[0-9]")
_NUMBER_SHAPE = re.compile(r"[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?")
_YEAR_SHAPE = re.compile(r"[0-9]{4}")
_AMOUNT_PREFIX = re.compile(r"(?<![^\W_])(?:US\$|USD|\$)\ ?$", re.IGNORECASE)
_AMOUNT_SCALE = re.compile(
    r"(?:mn|m|bn|k)(?![^\W_])|\ (?:thousand|million|billion)(?![^\W_])",
    re.IGNORECASE,
)
_AMOUNT_DOLLARS = re.compile(
    r"(?:\ (?:thousand|million|billion))?\ (?:US\ )?dollars(?![^\W_])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Number:
    start: int
    end: int
    text: str

    @property
    def value(self) -> Fraction:
        return Fraction(self.text.replace(",", ""))

    @property
    def has_decimal(self) -> bool:
        return "." in self.text


@dataclass(frozen=True)
class _Amount:
    start: int
    end: int
    value: Optional[int]  # whole US dollars, or None when not a whole number of dollars


def _whole_dollars(total: Fraction) -> Optional[int]:
    return total.numerator if total.denominator == 1 else None


def _scale_of(matched: str) -> int:
    return _SCALE_VALUES[matched.strip().lower()]


def _numbers(sentence: str) -> list[_Number]:
    """Number shapes (A.4) not joined to a preceding letter or digit.

    A letter directly after a number is allowed here, because an amount may take a scale
    directly after its number ('$12M'). Plain numbers also need a non-letter after them.
    """
    numbers = []
    for match in _NUMBER_TOKEN.finditer(sentence):
        token = match.group()
        if not _NUMBER_SHAPE.fullmatch(token) or _is_alnum_at(sentence, match.start() - 1):
            continue
        numbers.append(_Number(match.start(), match.end(), token))
    return numbers


def _amounts(sentence: str, numbers: list[_Number]) -> list[_Amount]:
    """Amounts (A.4): '$'/'US$'/'USD' forms, or a number followed by 'dollars'."""
    amounts = []
    for number in numbers:
        scale = 1
        prefix = _AMOUNT_PREFIX.search(sentence[: number.start])
        if prefix:
            start, end = prefix.start(), number.end
            scale_match = _AMOUNT_SCALE.match(sentence, number.end)
            if scale_match:
                end = scale_match.end()
                scale = _scale_of(scale_match.group())
        else:
            dollars = _AMOUNT_DOLLARS.match(sentence, number.end)
            if not dollars:
                continue
            start, end = number.start, dollars.end()
            scale_word = re.search(r"(thousand|million|billion)", dollars.group(), re.IGNORECASE)
            if scale_word:
                scale = _scale_of(scale_word.group())
        if _is_alnum_at(sentence, end):  # an amount has no letter or digit directly after it
            continue
        amounts.append(_Amount(start, end, _whole_dollars(number.value * scale)))
    return amounts


def _plain_numbers(sentence: str) -> list[_Number]:
    """Numbers that are not part of an amount."""
    numbers = _numbers(sentence)
    amounts = _amounts(sentence, numbers)
    return [
        number
        for number in numbers
        if not _is_alnum_at(sentence, number.end)
        and not any(a.start <= number.start < a.end for a in amounts)
    ]


def headcount_range_for(count: int) -> str:
    for upper, label in HEADCOUNT_RANGES:
        if count <= upper:
            return label
    return HEADCOUNT_TOP


# --------------------------------------------------------------- candidates


def _legal_name_values(sentence: str, domain: str) -> set[str]:
    values = set()
    for mention in company_mentions(domain):
        for match in find_phrase(sentence, mention):
            value = _legal_name_from(sentence, match.start(), match.end())
            if value is not None:
                values.add(value)
    return values


def _legal_name_from(sentence: str, start: int, pos: int) -> Optional[str]:
    """Shortest name + words + optional ',' + space + suffix starting at start."""
    n = len(sentence)
    while True:
        if sentence.startswith(" ", pos):
            end = _suffix_end(sentence, pos + 1)
            if end is not None:
                return sentence[start:end]
        if sentence.startswith(", ", pos):
            end = _suffix_end(sentence, pos + 2)
            if end is not None:
                return sentence[start:end]
        if pos < n and sentence[pos] == " ":
            word_end = _capitalised_word_end(sentence, pos + 1)
            if word_end is None:
                word_end = _uppercase_word_end(sentence, pos + 1)
            if word_end is not None:
                pos = word_end
                continue
        return None


def _capitalised_runs(text: str, joiners: str) -> list[tuple[int, int, int]]:
    """Maximal runs of capitalised words joined by one of the joiner characters.

    Each run is (start, end, word_count). The joiner must be a single character.
    """
    runs = []
    i = 0
    n = len(text)
    while i < n:
        end = _capitalised_word_end(text, i)
        if end is None:
            i += 1
            continue
        start, count = i, 1
        while end + 1 < n and text[end] in joiners:
            next_end = _capitalised_word_end(text, end + 1)
            if next_end is None:
                break
            end = next_end
            count += 1
        runs.append((start, end, count))
        i = end
    return runs


def _hq_city_values(sentence: str) -> set[str]:
    values = set()
    for phrase in STATEMENT_PHRASES["hq_city"]:
        for match in find_phrase(sentence, phrase):
            if not sentence.startswith(" ", match.end()):
                continue
            begin = match.end() + 1
            if _capitalised_word_end(sentence, begin) is None:
                continue
            runs = _capitalised_runs(sentence[begin:], " -")
            if runs and runs[0][0] == 0:
                values.add(sentence[begin : begin + runs[0][1]])
    return values


def _ceo_values(sentence: str, domain: str) -> set[str]:
    masked = list(sentence)
    for mention in company_mentions(domain):
        for match in find_phrase(sentence, mention):
            masked[match.start() : match.end()] = "\x00" * (match.end() - match.start())
    for phrase in STATEMENT_PHRASES["ceo"]:
        for match in find_phrase(sentence, phrase):
            masked[match.start() : match.end()] = "\x00" * (match.end() - match.start())
    text = "".join(masked)
    values = set()
    for start, end, count in _capitalised_runs(text, " "):
        if count in (2, 3):
            values.add(sentence[start:end])
    return values


def _founded_year_values(sentence: str) -> set[int]:
    values = set()
    for number in _plain_numbers(sentence):
        if _YEAR_SHAPE.fullmatch(number.text):
            year = int(number.text)
            if 1800 <= year <= 2099:
                values.add(year)
    return values


def _headcount_values(sentence: str) -> set[str]:
    values = set()
    for number in _plain_numbers(sentence):
        if number.has_decimal:
            continue
        count = number.value.numerator
        if count >= 1:
            values.add(headcount_range_for(count))
    return values


def _funding_values(sentence: str) -> set[int]:
    numbers = _numbers(sentence)
    return {a.value for a in _amounts(sentence, numbers) if a.value is not None}


def candidate_values(sentence: str, domain: str, field: str) -> set:
    """Every value in field's format that the sentence contains (A.4, A.5)."""
    if field == "legal_name":
        return _legal_name_values(sentence, domain)
    if field == "hq_city":
        return _hq_city_values(sentence)
    if field == "ceo":
        return _ceo_values(sentence, domain)
    if field == "founded_year":
        return _founded_year_values(sentence)
    if field == "headcount_range":
        return _headcount_values(sentence)
    if field == "funding_total":
        return _funding_values(sentence)
    raise ValueError(f"unknown field: {field}")


# ------------------------------------------------------------------ support


def supports(excerpt: str, domain: str, field: str):
    """The value the excerpt supports for field of the company, or None (A.2).

    Returns str for text fields and headcount_range, int for founded_year and funding_total.
    """
    sentences = split_sentences(excerpt)
    if len(sentences) != 1:
        return None
    sentence = sentences[0]
    if not names_company(sentence, domain):
        return None
    if not _has_any_phrase(sentence, STATEMENT_PHRASES[field]):
        return None
    if _has_any_phrase(sentence, NEGATING_PHRASES):
        return None
    values = candidate_values(sentence, domain, field)
    if len(values) != 1:
        return None
    return next(iter(values))


def page_claims(prose: str, domain: str) -> list[tuple[str, str, object]]:
    """(sentence, field, value) for every sentence of the prose that supports a value."""
    claims = []
    for line in prose.splitlines():
        for sentence in split_sentences(line):
            for field in FIELDS:
                value = supports(sentence, domain, field)
                if value is not None:
                    claims.append((sentence, field, value))
    return claims


# ------------------------------------------------------------------- pages


def _is_header_line(line: str) -> bool:
    name, separator, _ = line.partition(":")
    if not separator or not name:
        return False
    for segment in name.split("-"):
        if _capitalised_word_end(segment, 0) != len(segment):
            return False
    return True


def parse_page(text: str) -> tuple[dict[str, str], str]:
    """Split a page text into (header, prose) per §4.

    The header is the run of 'Name: value' lines before the first empty line. Non-header
    lines inside that run are dropped. A text whose first line is not a header line has
    no header and is all prose.
    """
    lines = text.splitlines()
    if not lines or not _is_header_line(lines[0]):
        return {}, text
    header: dict[str, str] = {}
    index = 0
    while index < len(lines) and lines[index].strip():
        if _is_header_line(lines[index]):
            name, _, value = lines[index].partition(":")
            header.setdefault(name, value.strip())
        index += 1
    prose = "\n".join(lines[index + 1 :])
    return header, prose


def facts_from_header(header: dict[str, str]) -> dict:
    """The JSON object of a 'Facts:' header line, or {} when absent or malformed (informative only)."""
    try:
        facts = json.loads(header.get("Facts", "{}"))
    except json.JSONDecodeError:
        return {}
    return facts if isinstance(facts, dict) else {}
