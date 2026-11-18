"""Per-field value formats (Appendix A.4), already normalised (A.5).

Every function takes the excerpt text and the company, and returns the list of
normalised values the excerpt contains in that field's format.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .numbers import amounts, numbers_outside_amounts
from .sentences import LEGAL_FORM_SUFFIXES
from .words import (
    alnum_runs, capitalised_runs, is_capitalised_word, is_uppercase_word,
    whole_word_pattern,
)

LEGAL_NAME = "legal_name"
HQ_CITY = "hq_city"
CEO = "ceo"
FOUNDED_YEAR = "founded_year"
HEADCOUNT_RANGE = "headcount_range"
FUNDING_TOTAL = "funding_total"

PHRASES = {
    LEGAL_NAME: ("legal name", "registered name", "registered as", "registered company",
                 "legal entity", "name of record"),
    HQ_CITY: ("headquartered in", "headquarters in", "head office in", "based in",
              "registered office in", "registered seat in"),
    CEO: ("chief executive officer", "chief executive", "CEO"),
    FOUNDED_YEAR: ("founded", "founding", "established", "incorporated"),
    HEADCOUNT_RANGE: ("employs", "employees", "staff", "people", "headcount", "workforce"),
    FUNDING_TOTAL: ("raised", "funding", "invested", "investment"),
}
NEGATING_PHRASES = (
    "in talks to", "plans to", "planning to", "wants to", "expects to", "hopes to",
    "aims to", "seeking", "could", "would", "might", "reportedly", "rumoured",
    "former", "formerly", "will become", "not",
)
HEADCOUNT_RANGES = (
    (1, 10, "1-10"), (11, 50, "11-50"), (51, 200, "51-200"), (201, 500, "201-500"),
    (501, 1000, "501-1000"), (1001, 5000, "1001-5000"), (5001, 10000, "5001-10000"),
)

_PHRASE_PATTERNS = {f: whole_word_pattern(p) for f, p in PHRASES.items()}
NEGATION_PATTERN = whole_word_pattern(NEGATING_PHRASES)
_SEPARATOR = "\x00"


@dataclass(frozen=True)
class Company:
    domain: str

    @property
    def name(self) -> str:
        return self.domain.split(".")[0].replace("-", " ")

    @property
    def names_pattern(self):
        return _names_pattern(self.name, self.domain)

    @property
    def removable_pattern(self):
        """Name and CEO phrases, taken out of a sentence before looking for a person."""
        return _removable_pattern(self.name)


@lru_cache(maxsize=4096)
def _names_pattern(name: str, domain: str):
    return whole_word_pattern([name, domain])


@lru_cache(maxsize=4096)
def _removable_pattern(name: str):
    return whole_word_pattern([name, *PHRASES[CEO]])


def phrase_pattern(field: str):
    return _PHRASE_PATTERNS[field]


def _legal_suffix_end(text: str, pos: int) -> int | None:
    if text[pos:pos + 1] == ",":
        pos += 1
    if text[pos:pos + 1] != " ":
        return None
    pos += 1
    ends = [
        pos + len(s) for s in LEGAL_FORM_SUFFIXES
        if text.startswith(s, pos) and not text[pos + len(s):pos + len(s) + 1].isalnum()
    ]
    return min(ends) if ends else None


def _word_end(text: str, pos: int) -> int | None:
    if text[pos:pos + 1] != " ":
        return None
    for start, end in alnum_runs(text):
        if start == pos + 1:
            word = text[start:end]
            return end if is_capitalised_word(word) or is_uppercase_word(word) else None
    return None


def legal_names(text: str, company: Company) -> list[str]:
    values = []
    for m in company.names_pattern.finditer(text):
        pos = m.end()
        while pos is not None:
            end = _legal_suffix_end(text, pos)
            if end is not None:
                values.append(text[m.start():end])
                break
            pos = _word_end(text, pos)
    return values


def hq_cities(text: str, company: Company) -> list[str]:
    runs = {s: e for s, e in capitalised_runs(text, " -")}
    values = []
    for m in phrase_pattern(HQ_CITY).finditer(text):
        start = m.end() + 1
        if text[m.end():start] == " " and start in runs:
            values.append(text[start:runs[start]])
    return values


def ceos(text: str, company: Company) -> list[str]:
    cleaned = company.removable_pattern.sub(_SEPARATOR, text)
    values = []
    for start, end in capitalised_runs(cleaned, " "):
        if 2 <= cleaned[start:end].count(" ") + 1 <= 3:
            values.append(cleaned[start:end])
    return values


def founded_years(text: str, company: Company) -> list[int]:
    return [
        int(n.text) for n in numbers_outside_amounts(text)
        if len(n.text) == 4 and n.text.isdigit() and 1800 <= int(n.text) <= 2099
    ]


def headcount_ranges(text: str, company: Company) -> list[str]:
    values = []
    for n in numbers_outside_amounts(text):
        if n.has_decimal or n.value < 1:
            continue
        values.append(_range_containing(int(n.value)))
    return values


def _range_containing(count: int) -> str:
    for low, high, label in HEADCOUNT_RANGES:
        if low <= count <= high:
            return label
    return "10001+"


def funding_totals(text: str, company: Company) -> list[int]:
    return [a.whole_dollars for a in amounts(text) if a.whole_dollars is not None]


EXTRACTORS = {
    LEGAL_NAME: legal_names,
    HQ_CITY: hq_cities,
    CEO: ceos,
    FOUNDED_YEAR: founded_years,
    HEADCOUNT_RANGE: headcount_ranges,
    FUNDING_TOTAL: funding_totals,
}
