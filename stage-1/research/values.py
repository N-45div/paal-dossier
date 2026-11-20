"""Value extractors for Appendix A.4 and their normalisation (A.5)."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from .fields import headcount_range_for
from .lexicon import LEGAL_SUFFIXES, SCALE_SUFFIXES, SCALE_WORDS, STATEMENT_PHRASES
from .matching import is_capitalised, is_uppercase_word, whole_words, word_at

# Marks an amount that does not come to a whole number of dollars. It is not a
# value, so an excerpt containing one can never agree on a single value.
NOT_WHOLE = None

_NUMBER_BODY = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
# A number is not joined to letters or digits, nor to digits by ',' or '.' in any other way.
_NUMBER = re.compile(r"(?<![^\W_])(?<!\d[.,])(?P<body>" + _NUMBER_BODY + r")(?![^\W_])(?![.,]\d)")
_AMOUNT_SYMBOL = re.compile(
    r"(?<![^\W_])(?:US\$|USD|\$) ?(?P<num>" + _NUMBER_BODY + r")"
    r"(?:(?P<suffix>mn|bn|k|m)|(?: (?P<word>thousand|million|billion)))?(?![^\W_])",
    re.IGNORECASE,
)
_AMOUNT_WORDS = re.compile(
    r"(?<![^\W_])(?<!\d[.,])(?P<num>" + _NUMBER_BODY + r")"
    r"(?: (?P<word>thousand|million|billion))? (?:US )?dollars(?![^\W_])",
    re.IGNORECASE,
)
_WORD_RUN = re.compile(r"(?<![^\W_])[^\W\d_]+(?![^\W_])")
_STATEMENT = {field: whole_words(phrases) for field, phrases in STATEMENT_PHRASES.items()}
_CEO_PHRASE = _STATEMENT["ceo"]
_LEGAL_SUFFIXES = tuple(LEGAL_SUFFIXES)


@dataclass(frozen=True)
class Span:
    start: int
    end: int

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end


Amount = tuple[Span, int | None]


def company_pattern(domain: str) -> re.Pattern[str]:
    """The company's normalised domain or its name (first label, '-' read as a space), whole words."""
    name = domain.split(".", 1)[0].replace("-", " ")
    return whole_words([domain, name])


def statement_present(field: str, sentence: str) -> bool:
    return _STATEMENT[field].search(sentence) is not None


def find_amounts(sentence: str) -> list[Amount]:
    """Amounts in the sentence with their value in dollars (NOT_WHOLE when not whole)."""
    found: list[Amount] = []
    taken: list[Span] = []
    for pattern in (_AMOUNT_SYMBOL, _AMOUNT_WORDS):
        for match in pattern.finditer(sentence):
            span = Span(match.start(), match.end())
            if any(span.overlaps(other) for other in taken):
                continue
            taken.append(span)
            found.append((span, _amount_dollars(match)))
    return found


def _amount_dollars(match: re.Match[str]) -> int | None:
    groups = match.groupdict()
    scale = 1
    if groups.get("suffix"):
        scale = SCALE_SUFFIXES[groups["suffix"].lower()]
    elif groups.get("word"):
        scale = SCALE_WORDS[groups["word"].lower()]
    dollars = Decimal(groups["num"].replace(",", "")) * scale
    return int(dollars) if dollars == dollars.to_integral_value() else NOT_WHOLE


def _numbers_outside_amounts(sentence: str, amounts: Iterable[Amount]) -> list[re.Match[str]]:
    spans = [span for span, _ in amounts]
    return [
        match
        for match in _NUMBER.finditer(sentence)
        if not any(Span(match.start(), match.end()).overlaps(span) for span in spans)
    ]


def founded_years(sentence: str, amounts: Iterable[Amount]) -> set[int]:
    values: set[int] = set()
    for match in _numbers_outside_amounts(sentence, amounts):
        text = match.group("body")
        if re.fullmatch(r"\d{4}", text) and 1800 <= int(text) <= 2099:
            values.add(int(text))
    return values


def headcount_ranges(sentence: str, amounts: Iterable[Amount]) -> set[str]:
    values: set[str] = set()
    for match in _numbers_outside_amounts(sentence, amounts):
        text = match.group("body")
        if "." in text:
            continue
        label = headcount_range_for(int(text.replace(",", "")))
        if label is not None:
            values.add(label)
    return values


def funding_totals(amounts: Iterable[Amount]) -> set[int | None]:
    return {dollars for _, dollars in amounts}


def legal_names(sentence: str, company: re.Pattern[str]) -> set[str]:
    """For each company mention, the shortest 'name [Words] [,] suffix' that starts there."""
    values: set[str] = set()
    for match in company.finditer(sentence):
        end = _shortest_legal_end(sentence, match.end())
        if end is not None:
            values.add(sentence[match.start() : end])
    return values


def _shortest_legal_end(sentence: str, pos: int) -> int | None:
    ends: list[int] = []
    cursor = pos
    while True:
        for lead in (", ", " "):
            if sentence.startswith(lead, cursor):
                ends.extend(_suffix_ends(sentence, cursor + len(lead)))
        if not sentence.startswith(" ", cursor):
            break
        word = word_at(sentence, cursor + 1)
        if word is None or not (is_capitalised(word.group()) or is_uppercase_word(word.group())):
            break
        cursor = word.end()
    return min(ends) if ends else None


def _suffix_ends(sentence: str, pos: int) -> list[int]:
    ends = []
    for suffix in _LEGAL_SUFFIXES:
        end = pos + len(suffix)
        if sentence.startswith(suffix, pos) and not (end < len(sentence) and sentence[end].isalnum()):
            ends.append(end)
    return ends


def headquarters_cities(sentence: str) -> set[str]:
    """For each statement phrase followed by one space, the longest capitalised-word run after it."""
    values: set[str] = set()
    for match in _STATEMENT["hq_city"].finditer(sentence):
        if not sentence.startswith(" ", match.end()):
            continue
        start = match.end() + 1
        end = _capitalised_run_end(sentence, start, joiners=" -")
        if end is not None:
            values.add(sentence[start:end])
    return values


def _capitalised_run_end(text: str, pos: int, joiners: str) -> int | None:
    """End of the run of capitalised words starting at pos and joined by single joiner characters."""
    word = word_at(text, pos)
    if word is None or not is_capitalised(word.group()):
        return None
    end = word.end()
    while end < len(text) and text[end] in joiners:
        following = word_at(text, end + 1)
        if following is None or not is_capitalised(following.group()):
            break
        end = following.end()
    return end


def ceo_names(sentence: str, company: re.Pattern[str]) -> set[str]:
    """Runs of two or three capitalised words joined by single spaces, after the company name and CEO phrases are masked."""
    masked = _CEO_PHRASE.sub("\x00", company.sub("\x00", sentence))
    names: set[str] = set()
    for start, end, count in _space_joined_runs(masked):
        if 2 <= count <= 3:
            names.add(masked[start:end])
    return names


def _space_joined_runs(text: str) -> list[tuple[int, int, int]]:
    """Maximal runs of capitalised words joined by single spaces, as (start, end, word count)."""
    runs: list[list[int]] = []
    for match in _WORD_RUN.finditer(text):
        if not is_capitalised(match.group()):
            continue
        if runs and runs[-1][1] + 1 == match.start() and text[runs[-1][1]] == " ":
            runs[-1][1] = match.end()
            runs[-1][2] += 1
        else:
            runs.append([match.start(), match.end(), 1])
    return [(start, end, count) for start, end, count in runs]
