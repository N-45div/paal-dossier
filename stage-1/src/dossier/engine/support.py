"""Appendix A: when an excerpt supports a value of a dossier field.

``supported_values`` is the whole definition of "supports" used by the service: it returns
every (field, value) pair that one excerpt states for a company, and nothing else.
"""

from __future__ import annotations

import bisect
import re
from decimal import Decimal
from functools import lru_cache
from typing import NamedTuple

from .pages import collapse_whitespace, sentences
from .terms import (
    AFTER_WORD,
    BEFORE_WORD,
    CAP_WORD,
    NEGATING_PHRASES,
    NUMBER,
    NUMBER_AFTER,
    NUMBER_BEFORE,
    SCALE_FACTORS,
    STATEMENT_PHRASES,
    UPPER_WORD,
    phrase_alternation,
    suffix_alternation,
    whole_phrases,
)

FIELDS: tuple[str, ...] = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)

# Headcount ranges of §4 with their upper bounds; above the last one is "10001+".
_HEADCOUNT_RANGES: tuple[tuple[int, str], ...] = (
    (10, "1-10"),
    (50, "11-50"),
    (200, "51-200"),
    (500, "201-500"),
    (1000, "501-1000"),
    (5000, "1001-5000"),
    (10000, "5001-10000"),
)
_CEO_PHRASES = STATEMENT_PHRASES["ceo"]
_HQ_PHRASES = STATEMENT_PHRASES["hq_city"]
_SEPARATOR = "\x00"  # stands where a company name or CEO phrase was taken out of a sentence

_STATEMENT_PATTERNS: dict[str, re.Pattern[str]] = {
    field: whole_phrases(phrases) for field, phrases in STATEMENT_PHRASES.items()
}
_NEGATION = whole_phrases(NEGATING_PHRASES)
_CEO_PHRASE = whole_phrases(_CEO_PHRASES)
_HQ_PLACE = re.compile(
    rf"{BEFORE_WORD}{phrase_alternation(_HQ_PHRASES)}{AFTER_WORD}"
    rf" (?P<place>{CAP_WORD}(?:[ -]{CAP_WORD})*)"
)
_PERSON = re.compile(rf"{CAP_WORD}(?: {CAP_WORD})*")
_NUMBER_TOKEN = re.compile(rf"{NUMBER_BEFORE}(?P<token>{NUMBER}){NUMBER_AFTER}")
_AMOUNT = re.compile(
    rf"(?:"
    rf"{BEFORE_WORD}(?i:US\$|USD|\$) ?(?P<sym>{NUMBER})"
    rf"(?:(?P<scale>(?i:mn|bn|k|m))|(?: (?P<word>(?i:thousand|million|billion))))?"
    rf"|{NUMBER_BEFORE}(?P<num>{NUMBER})"
    rf"(?: (?P<scale2>(?i:thousand|million|billion)))? (?:(?i:US) )?(?i:dollars)"
    rf"){NUMBER_AFTER}"
)


class _Span(NamedTuple):
    start: int
    end: int


class _Amount(NamedTuple):
    span: _Span
    value: int | None  # None when the amount is not a whole number of dollars


class _Company(NamedTuple):
    domain: str
    name: re.Pattern[str]  # the name alone, for ceo sentences (A.4)
    mention: re.Pattern[str]  # the name or the domain (A.2 rule 2)
    legal_name: re.Pattern[str]  # legal_name values (A.4)


@lru_cache(maxsize=512)
def _company(domain: str) -> _Company:
    """Patterns for one company; ``domain`` is normalised and lower case."""
    name = domain.split(".", 1)[0].replace("-", " ")
    name_alt = f"(?i:{re.escape(name)})"
    mention_alt = f"(?i:{re.escape(name)}|{re.escape(domain)})"
    legal = (
        rf"{BEFORE_WORD}{mention_alt}"
        rf"(?:[ ](?:{CAP_WORD}|{UPPER_WORD}))*?,? {suffix_alternation()}{AFTER_WORD}"
    )
    return _Company(
        domain=domain,
        name=re.compile(BEFORE_WORD + name_alt + AFTER_WORD),
        mention=re.compile(BEFORE_WORD + mention_alt + AFTER_WORD),
        legal_name=re.compile(legal),
    )


def supported_values(excerpt: str, domain: str) -> list[tuple[str, str | int]]:
    """Every (field, normalised value) that ``excerpt`` supports for the company ``domain``.

    ``domain`` is the company's normalised domain. Values are ``int`` for ``founded_year``
    and ``funding_total`` and ``str`` for the other fields.
    """
    sentence = collapse_whitespace(excerpt)
    company = _company(domain.lower())
    if len(sentences(sentence)) != 1:
        return []
    if _NEGATION.search(sentence) or not company.mention.search(sentence):
        return []
    amounts = _amounts(sentence)
    numbers = _numbers_outside(sentence, amounts)
    supported: list[tuple[str, str | int]] = []
    for field in FIELDS:
        if not _STATEMENT_PATTERNS[field].search(sentence):
            continue
        values = _field_values(field, sentence, company, amounts, numbers)
        distinct = set(values)
        if len(distinct) == 1:
            supported.append((field, distinct.pop()))
    return supported


EXCERPT_MAX_CHARS = 500


FRAGMENT_SENTENCE_MAX_CHARS = 50000  # longer sentences are not searched for a fragment
FRAGMENT_CHECKS_PER_SENTENCE = 2000  # most supports() calls one sentence may cost
FRAGMENT_CHECKS_PER_BUILD = 4000  # most supports() calls one build may spend on fragments
FRAGMENT_SENTENCES_PER_BUILD = 500  # most long sentences one build searches


class FragmentBudget:
    """The fragment search work one build may do. A search that runs out stops early, and
    the value it would have cited is simply not cited; the build is not failed."""

    def __init__(
        self,
        checks: int = FRAGMENT_CHECKS_PER_BUILD,
        sentences: int = FRAGMENT_SENTENCES_PER_BUILD,
    ) -> None:
        self.checks = checks
        self.sentences = sentences

    def start_sentence(self) -> bool:
        if self.sentences <= 0 or self.checks <= 0:
            return False
        self.sentences -= 1
        return True

    def spend_check(self) -> bool:
        if self.checks <= 0:
            return False
        self.checks -= 1
        return True


def supporting_excerpts(
    text: str, domain: str, budget: FragmentBudget | None = None
) -> list[tuple[str, str | int, str]]:
    """Each (field, value, excerpt) that ``text`` supports, with the text cited for it.

    ``text`` is one sentence of served prose. A supported value is cited with the sentence
    when it fits in EXCERPT_MAX_CHARS. A longer sentence of at most
    FRAGMENT_SENTENCE_MAX_CHARS cites the shortest contiguous fragment that supports the
    value on its own, and only when the whole sentence supports the value (a conflicting
    value or a negating phrase in the sentence blocks it). ``budget`` bounds the fragment
    work of a build; None means unbounded.
    """
    sentence = collapse_whitespace(text)
    found: list[tuple[str, str | int, str]] = []
    for field, value in supported_values(sentence, domain):
        if len(sentence) <= EXCERPT_MAX_CHARS:
            found.append((field, value, sentence))
            continue
        if len(sentence) > FRAGMENT_SENTENCE_MAX_CHARS:
            continue
        if budget is not None and not budget.start_sentence():
            continue
        fragment = _shortest_fragment(sentence, domain, field, value, budget)
        if fragment is not None:
            found.append((field, value, fragment))
    return found


def _shortest_fragment(
    sentence: str,
    domain: str,
    field: str,
    value: str | int,
    budget: FragmentBudget | None,
) -> str | None:
    """The shortest window of ``sentence`` that supports ``value`` for ``field``.

    A supporting window contains a company mention and a statement phrase, so it starts at
    or before the earlier of the two and ends at or after the later one. Windows are
    generated by length, shortest first, from word boundaries: for each length, each pair of
    anchors, and each word-boundary start in range, the window of that length is checked.
    Nothing is materialised or sorted, and the first window that passes ``supports`` is
    returned. Each supports() call is counted against FRAGMENT_CHECKS_PER_SENTENCE and the
    build's budget.
    """
    company = _company(domain.lower())
    mentions = [m.span() for m in company.mention.finditer(sentence)]
    phrases = [m.span() for m in _STATEMENT_PATTERNS[field].finditer(sentence)]
    pairs = sorted(
        {
            (min(mention[0], phrase[0]), max(mention[1], phrase[1]))
            for mention in mentions
            for phrase in phrases
            if max(mention[1], phrase[1]) - min(mention[0], phrase[0]) <= EXCERPT_MAX_CHARS
        }
    )
    if not pairs:
        return None
    word_starts = [m.start() for m in re.finditer(r"\S+", sentence)]
    word_ends = {m.end() for m in re.finditer(r"\S+", sentence)}
    checked: set[tuple[int, int]] = set()
    for length in range(1, EXCERPT_MAX_CHARS + 1):
        for low, high in pairs:
            if length < high - low:
                continue
            first = bisect.bisect_left(word_starts, high - length)
            last = bisect.bisect_right(word_starts, low)
            for start in word_starts[first:last]:
                end = start + length
                if end not in word_ends or (start, end) in checked:
                    continue
                checked.add((start, end))
                if len(checked) > FRAGMENT_CHECKS_PER_SENTENCE:
                    return None
                if budget is not None and not budget.spend_check():
                    return None
                fragment = sentence[start:end]
                if supports(fragment, domain, field, value):
                    return fragment
    return None


def supports(excerpt: str, domain: str, field: str, value: str | int) -> bool:
    """Whether ``excerpt`` supports ``value`` for ``field`` of the company ``domain``."""
    return any(
        name == field and str(found) == str(value)
        for name, found in supported_values(excerpt, domain)
    )


def _field_values(
    field: str,
    sentence: str,
    company: _Company,
    amounts: list[_Amount],
    numbers: list[tuple[_Span, str]],
) -> list[str | int]:
    """Every value of ``field``'s format that the sentence contains (A.4, A.5)."""
    if field == "legal_name":
        return [match.group(0) for match in company.legal_name.finditer(sentence)]
    if field == "hq_city":
        return [match.group("place") for match in _HQ_PLACE.finditer(sentence)]
    if field == "ceo":
        return _person_names(sentence, company)
    if field == "founded_year":
        return [
            int(token)
            for _, token in numbers
            if re.fullmatch(r"[0-9]{4}", token) and 1800 <= int(token) <= 2099
        ]
    if field == "headcount_range":
        return [
            _headcount_range(int(token.replace(",", "")))
            for _, token in numbers
            if "." not in token and int(token.replace(",", "")) >= 1
        ]
    return [amount.value for amount in amounts if amount.value is not None]


def _person_names(sentence: str, company: _Company) -> list[str]:
    """Runs of two or three capitalised words, once the company name and CEO phrases are out."""
    text = company.name.sub(_SEPARATOR, sentence)
    text = _CEO_PHRASE.sub(_SEPARATOR, text)
    return [
        match.group(0)
        for match in _PERSON.finditer(text)
        if match.group(0).count(" ") in (1, 2)
    ]


def _headcount_range(count: int) -> str:
    for upper, label in _HEADCOUNT_RANGES:
        if count <= upper:
            return label
    return "10001+"


def _amounts(sentence: str) -> list[_Amount]:
    """Every amount of the sentence (A.4), with its value in dollars when it is whole."""
    found: list[_Amount] = []
    for match in _AMOUNT.finditer(sentence):
        number = match.group("sym") or match.group("num")
        scale_word = (
            match.group("scale") or match.group("word") or match.group("scale2") or ""
        ).lower()
        factor = SCALE_FACTORS.get(scale_word, 1)
        dollars = Decimal(number.replace(",", "")) * factor
        whole = dollars == dollars.to_integral_value()
        found.append(
            _Amount(_Span(match.start(), match.end()), int(dollars) if whole else None)
        )
    return found


def _numbers_outside(
    sentence: str, amounts: list[_Amount]
) -> list[tuple[_Span, str]]:
    """Number tokens that are not part of an amount (A.4)."""
    numbers: list[tuple[_Span, str]] = []
    for match in _NUMBER_TOKEN.finditer(sentence):
        span = _Span(match.start(), match.end())
        if not any(_overlaps(span, amount.span) for amount in amounts):
            numbers.append((span, match.group("token")))
    return numbers


def _overlaps(first: _Span, second: _Span) -> bool:
    return first.start < second.end and second.start < first.end
