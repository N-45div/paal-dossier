"""When an excerpt supports a value: the whole of Appendix A, as pure functions."""

from __future__ import annotations

import re
from collections.abc import Callable

from app.research.numbers import find_amounts, find_numbers, headcount_range
from app.research.text import (
    LEGAL_SUFFIXES,
    alternation_pattern,
    collapse_whitespace,
    is_capitalised_word,
    is_single_sentence,
    is_uppercase_word,
    tokens,
    whole_word_pattern,
)

FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
Value = str | int

STATEMENT_PHRASES = {
    "legal_name": ["legal name", "registered name", "registered as", "registered company", "legal entity", "name of record"],
    "hq_city": ["headquartered in", "headquarters in", "head office in", "based in", "registered office in", "registered seat in"],
    "ceo": ["chief executive officer", "chief executive", "CEO"],
    "founded_year": ["founded", "founding", "established", "incorporated"],
    "headcount_range": ["employs", "employees", "staff", "people", "headcount", "workforce"],
    "funding_total": ["raised", "funding", "invested", "investment"],
}  # fmt: skip
NEGATING_PHRASES = [
    "in talks to", "plans to", "planning to", "wants to", "expects to", "hopes to", "aims to",
    "seeking", "could", "would", "might", "reportedly", "rumoured", "former", "formerly",
    "will become", "not",
]  # fmt: skip

_STATEMENT_PATTERNS = {f: [whole_word_pattern(p) for p in phrases] for f, phrases in STATEMENT_PHRASES.items()}
_NEGATING_PATTERNS = [whole_word_pattern(p) for p in NEGATING_PHRASES]
_CEO_REMOVABLE = alternation_pattern(STATEMENT_PHRASES["ceo"])
_SEPARATOR = "\x00"


def company_name(domain: str) -> str:
    """The first label of the domain with each ``-`` read as a space."""
    return domain.split(".")[0].replace("-", " ")


def _contains_any(patterns: list[re.Pattern[str]], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def _capitalised_runs(text: str, joiners: tuple[str, ...]) -> list[tuple[int, int]]:
    """Maximal runs of capitalised words joined by one of ``joiners``, as (start, end) spans."""
    runs: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None
    for match in tokens(text):
        if not is_capitalised_word(match.group()):
            if current:
                runs.append(current)
            current = None
        elif current and text[current[1] : match.start()] in joiners:
            current = (current[0], match.end())
        else:
            if current:
                runs.append(current)
            current = (match.start(), match.end())
    if current:
        runs.append(current)
    return runs


def _run_count(text: str, span: tuple[int, int]) -> int:
    return sum(1 for _ in tokens(text[span[0] : span[1]]))


def _ceo_values(sentence: str, domain: str) -> list[str]:
    removable = alternation_pattern([company_name(domain), *STATEMENT_PHRASES["ceo"]])
    cleaned = removable.sub(_SEPARATOR, sentence)
    values = []
    for span in _capitalised_runs(cleaned, (" ",)):
        if 2 <= _run_count(cleaned, span) <= 3:
            values.append(cleaned[span[0] : span[1]])
    return values


def _hq_city_values(sentence: str, domain: str) -> list[str]:
    values = []
    runs = _capitalised_runs(sentence, (" ", "-"))
    starts = {start: end for start, end in runs}
    for pattern in _STATEMENT_PATTERNS["hq_city"]:
        for match in pattern.finditer(sentence):
            begin = match.end() + 1
            if sentence[match.end() : begin] == " " and begin in starts:
                values.append(sentence[begin : starts[begin]])
    return values


def _suffix_end(sentence: str, index: int) -> int | None:
    """End of the shortest legal-form suffix at ``index`` with no letter or digit after it."""
    ends = []
    for suffix in LEGAL_SUFFIXES:
        end = index + len(suffix)
        if sentence.startswith(suffix, index) and (end >= len(sentence) or not sentence[end].isalnum()):
            ends.append(end)
    return min(ends) if ends else None


def _legal_name_from(sentence: str, name_end: int) -> int | None:
    """End of the shortest legal-name text whose company name ends at ``name_end``."""
    position = name_end
    while True:
        for lead in (", ", " "):
            if sentence.startswith(lead, position):
                end = _suffix_end(sentence, position + len(lead))
                if end is not None:
                    return end
        if not sentence.startswith(" ", position):
            return None
        word = next(tokens(sentence[position + 1 :]), None)
        if word is None or word.start() != 0:
            return None
        if not (is_capitalised_word(word.group()) or is_uppercase_word(word.group())):
            return None
        position += 1 + word.end()


def _legal_name_values(sentence: str, domain: str) -> list[str]:
    starts = alternation_pattern([company_name(domain), domain])
    values = []
    for match in starts.finditer(sentence):
        end = _legal_name_from(sentence, match.end())
        if end is not None:
            values.append(sentence[match.start() : end])
    return values


def _founded_year_values(sentence: str, domain: str) -> list[int]:
    numbers = find_numbers(sentence)
    in_amount = {a.number.start for a in find_amounts(sentence)}
    return [
        int(n.value)
        for n in numbers
        if n.start not in in_amount and re.fullmatch(r"[0-9]{4}", n.text.replace(",", "")) and 1800 <= int(n.value) <= 2099
    ]


def _headcount_values(sentence: str, domain: str) -> list[str]:
    numbers = find_numbers(sentence)
    in_amount = {a.number.start for a in find_amounts(sentence)}
    return [
        headcount_range(int(n.value))
        for n in numbers
        if n.start not in in_amount and not n.has_decimal_part and n.value >= 1
    ]


def _funding_values(sentence: str, domain: str) -> list[int]:
    amounts = find_amounts(sentence)
    return [d for a in amounts if (d := a.whole_dollars) is not None]


_VALUE_FINDERS: dict[str, Callable[[str, str], list[Value]]] = {
    "legal_name": _legal_name_values,
    "hq_city": _hq_city_values,
    "ceo": _ceo_values,
    "founded_year": _founded_year_values,
    "headcount_range": _headcount_values,
    "funding_total": _funding_values,
}  # type: ignore[assignment]


def _names_company(sentence: str, domain: str) -> bool:
    return _contains_any([whole_word_pattern(domain), whole_word_pattern(company_name(domain))], sentence)


def supported_values(excerpt: str, domain: str) -> dict[str, Value]:
    """The value of every field the excerpt supports, read on its own (A.2).

    An excerpt supports at most one value per field, so the result maps field to value.
    """
    sentence = collapse_whitespace(excerpt).strip()
    if not sentence or not is_single_sentence(sentence) or not _names_company(sentence, domain):
        return {}
    if _contains_any(_NEGATING_PATTERNS, sentence):
        return {}
    supported: dict[str, Value] = {}
    for field in FIELDS:
        if not _contains_any(_STATEMENT_PATTERNS[field], sentence):
            continue
        values = _VALUE_FINDERS[field](sentence, domain)
        if values and all(v == values[0] for v in values):
            supported[field] = values[0]
    return supported


def supports(excerpt: str, domain: str, field: str, value: Value) -> bool:
    """True when the excerpt supports ``value`` for ``field`` of the company at ``domain``."""
    found = supported_values(excerpt, domain).get(field)
    return found is not None and found == value and type(found) is type(value)
