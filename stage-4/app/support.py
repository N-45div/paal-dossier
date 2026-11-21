"""Pure rules of Dossier stage 1: page headers, excerpt sentences and Appendix A support.

No IO happens here. The public surface (Rul-2) is:

- ``FIELDS``                       the six dossier field names (§4)
- ``split_header(text)``           header lines and prose of a page text (§4 Pages)
- ``prose_sentences(prose)``       single-sentence excerpts of a page's prose (A.1)
- ``supported_values(domain, e)``  field -> normalised value for each field the excerpt
                                   supports under A.2
- ``extract_supports(domain, p)``  ``Support`` records for every sentence of the prose
- ``excerpt_in_prose(prose, e)``   a citation is a verbatim copy of prose (§4 Evidence)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

FIELDS: tuple[str, ...] = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)

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
    "headcount_range": ("employs", "employees", "staff", "people", "headcount", "workforce"),
    "funding_total": ("raised", "funding", "invested", "investment"),
}

# Stage 3 executives (Appendix A for each title, with the format of `ceo`): the title's
# statement phrases. The field `executives` is built from these, one person per title.
TITLES: tuple[str, ...] = ("cfo", "coo", "cto")
TITLE_PHRASES: dict[str, tuple[str, ...]] = {
    "cfo": ("chief financial officer", "CFO"),
    "coo": ("chief operating officer", "COO"),
    "cto": ("chief technology officer", "CTO"),
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

# Legal-form suffixes, matched exactly as written (case-sensitive), longest first.
LEGAL_SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        (
            "Inc.", "Corp.", "LLC", "LLP", "L.P.", "Ltd", "Limited", "Pty Ltd", "plc", "PLC",
            "GmbH", "AG", "KG", "SE", "AS", "A/S", "ASA", "AB", "Oy", "Oyj", "B.V.", "N.V.",
            "S.A.", "S.A.S.", "S.L.", "S.r.l.", "S.p.A.", "s.r.o.", "a.s.", "K.K.",
        ),
        key=len,
        reverse=True,
    )
)

# §4 headcount ranges: (label, lowest, highest); highest None means no upper bound.
HEADCOUNT_RANGES: tuple[tuple[str, int, int | None], ...] = (
    ("1-10", 1, 10),
    ("11-50", 11, 50),
    ("51-200", 51, 200),
    ("201-500", 201, 500),
    ("501-1000", 501, 1000),
    ("1001-5000", 1001, 5000),
    ("5001-10000", 5001, 10000),
    ("10001+", 10001, None),
)

MAX_EXCERPT_LENGTH = 500

_SCALES: dict[str, int] = {
    "": 1,
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "mn": 1_000_000,
    "million": 1_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
}

_TERMINATORS = ".!?"
_CLOSERS = "\"”’)"

# A whole word: no letter or digit directly before or after (A.2).
_BEFORE = r"(?<![^\W_])"
_AFTER = r"(?![^\W_])"

_LETTER_RUN = re.compile(r"[^\W\d_]+")
_HEADER_LINE = re.compile(r"([A-Z][A-Za-z]*(?:-[A-Z][A-Za-z]*)*):[ \t]*(.*)")

# A number (A.4): optional comma groups, optional decimal part, not joined to digits.
_NUMBER_BODY = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?(?![.,][0-9])"
_NUMBER_RE = re.compile(
    r"(?<![^\W_])(?<!\d[.,])(?P<num>" + _NUMBER_BODY + r")" + _AFTER
)

# An amount (A.4): dollar-sign form, or number followed by "dollars".
_AMOUNT_RE = re.compile(
    _BEFORE
    + r"(?:"
    + r"(?:US\$|USD|\$) ?(?P<n1>" + _NUMBER_BODY + r")"
    + r"(?:(?P<s1>mn|bn|k|m)|(?: (?P<w1>thousand|million|billion)))?"
    + r"|(?P<n2>" + _NUMBER_BODY + r")"
    + r"(?: (?P<w2>thousand|million|billion))? (?:US )?dollars"
    + r")"
    + _AFTER,
    re.IGNORECASE,
)


def _phrase_source(phrase: str) -> str:
    return " ".join(re.escape(word) for word in phrase.split(" "))


def _word_re(phrases: tuple[str, ...]) -> re.Pattern[str]:
    """Case-insensitive whole-word match of any phrase; longest phrase wins."""
    alternatives = "|".join(_phrase_source(p) for p in sorted(phrases, key=len, reverse=True))
    return re.compile(_BEFORE + "(?:" + alternatives + ")" + _AFTER, re.IGNORECASE)


_STATEMENT_RE = {field: _word_re(phrases) for field, phrases in STATEMENT_PHRASES.items()}
_NEGATION_RE = _word_re(NEGATING_PHRASES)
_FOUR_DIGITS_RE = re.compile(r"[0-9]{4}")


def _collapse(text: str) -> str:
    """Write every run of whitespace as one space and strip the ends."""
    return " ".join(text.split())


def _is_alnum_at(text: str, index: int) -> bool:
    return 0 <= index < len(text) and text[index].isalnum()


def _ends_with_suffix(line: str, dot: int) -> bool:
    """True when the '.' at ``dot`` ends a legal-form suffix written as a whole word (A.1)."""
    for suffix in LEGAL_SUFFIXES:
        if not suffix.endswith("."):
            continue  # only a dot that is part of a suffix written with its dot is exempt
        core = suffix[:-1]
        start = dot - len(core)
        if start >= 0 and line[start:dot] == core and not _is_alnum_at(line, start - 1):
            return True
    return False


def _segments(line: str) -> list[str]:
    """Cut one line into sentences at terminators followed by whitespace (A.1)."""
    bounds = [0]
    index = 0
    length = len(line)
    while index < length:
        if line[index] in _TERMINATORS:
            end = index + 1
            while end < length and line[end] in _CLOSERS:
                end += 1
            splits = end < length and line[end].isspace()
            if splits and not (line[index] == "." and _ends_with_suffix(line, index)):
                bounds.append(end)
            index = end
        else:
            index += 1
    bounds.append(length)
    return [line[a:b] for a, b in zip(bounds, bounds[1:])]


def split_sentences(line: str) -> list[str]:
    """Sentences of one line, each collapsed to single spaces, empty ones dropped (A.1)."""
    sentences = (_collapse(segment) for segment in _segments(line))
    return [sentence for sentence in sentences if sentence]


def prose_sentences(prose: str) -> list[str]:
    """Sentences of a page's prose: split at line breaks first, then into sentences (A.1)."""
    sentences: list[str] = []
    for line in prose.splitlines():
        sentences.extend(split_sentences(line))
    return sentences


def split_header(text: str) -> tuple[dict[str, str], str]:
    """Return ``(headers, prose)`` of a page text (§4 Pages).

    A text whose first line is not a header line has no header and is all prose.
    Otherwise the header runs to the first empty line; header lines inside it are
    recorded (first occurrence of a name wins) and the rest is the prose.
    """
    lines = text.splitlines()
    if not lines or _HEADER_LINE.fullmatch(lines[0]) is None:
        return {}, text
    headers: dict[str, str] = {}
    index = 0
    while index < len(lines) and lines[index].strip():
        match = _HEADER_LINE.fullmatch(lines[index])
        if match is not None:
            headers.setdefault(match.group(1), match.group(2).strip())
        index += 1
    prose = "\n".join(lines[index + 1 :]) if index < len(lines) else ""
    return headers, prose


def excerpt_in_prose(prose: str, excerpt: str) -> bool:
    """True when ``excerpt`` is a copy of text in ``prose``, runs of whitespace collapsible.

    The excerpt must be 1 to 500 characters long and must not start or end with
    whitespace.
    """
    if not isinstance(excerpt, str) or not 1 <= len(excerpt) <= MAX_EXCERPT_LENGTH:
        return False
    if excerpt != excerpt.strip():
        return False
    pattern = r"\s+".join(re.escape(part) for part in excerpt.split())
    return re.search(pattern, prose) is not None


def company_name(domain: str) -> str:
    """The first label of the domain with each '-' read as a space (A.2)."""
    return domain.split(".")[0].replace("-", " ")


def _is_capitalised(word: str) -> bool:
    return len(word) >= 2 and word[0].isupper() and word[1:].islower()


def _is_uppercase(word: str) -> bool:
    return len(word) >= 2 and word.isupper()


def _word_at(text: str, index: int) -> str | None:
    """The letter run starting at ``index``, or None when a digit follows it."""
    match = _LETTER_RUN.match(text, index)
    if match is None or (match.end() < len(text) and text[match.end()].isdigit()):
        return None
    return match.group()


def _suffix_end(text: str, index: int) -> int | None:
    """End of a legal-form suffix starting at ``index`` with no letter or digit after it."""
    for suffix in LEGAL_SUFFIXES:
        if text.startswith(suffix, index) and not _is_alnum_at(text, index + len(suffix)):
            return index + len(suffix)
    return None


def _legal_name_values(text: str, domain: str, name: str) -> set[str]:
    """Each name or domain, then capitalised/uppercase words, then a legal suffix (A.4).

    Where several texts start at the same place, the shortest is taken.
    """
    values: set[str] = set()
    for match in _word_re((domain, name)).finditer(text):
        position = match.end()
        while True:
            end = None
            for separator in (", ", " "):
                if text.startswith(separator, position):
                    end = _suffix_end(text, position + len(separator))
                    if end is not None:
                        break
            if end is not None:
                values.add(text[match.start() : end])
                break
            if not text.startswith(" ", position):
                break
            word = _word_at(text, position + 1)
            if word is None or not (_is_capitalised(word) or _is_uppercase(word)):
                break
            position += 1 + len(word)
    return values


def _hq_city_values(text: str) -> set[str]:
    """The longest run of capitalised words joined by spaces or '-' after a phrase (A.4)."""
    values: set[str] = set()
    for match in _STATEMENT_RE["hq_city"].finditer(text):
        if not text.startswith(" ", match.end()):
            continue
        start = match.end() + 1
        word = _word_at(text, start)
        if word is None or not _is_capitalised(word):
            continue
        end = start + len(word)
        while end < len(text) and text[end] in " -":
            following = _word_at(text, end + 1)
            if following is None or not _is_capitalised(following):
                break
            end += 1 + len(following)
        values.add(text[start:end])
    return values


def _ceo_values(text: str, domain: str, name: str) -> set[str]:
    """Runs of two or three capitalised words once the company and CEO phrases are removed."""
    return _person_values(text, domain, name, _STATEMENT_RE["ceo"])


def _person_values(text: str, domain: str, name: str, phrase_re: re.Pattern[str]) -> set[str]:
    """Runs of two or three capitalised words once the company and the title's phrases are removed."""
    masked = _word_re((domain, name)).sub("|", text)
    masked = phrase_re.sub("|", masked)
    runs: list[list[str]] = []
    run: list[str] = []
    previous_end = -2
    for match in _LETTER_RUN.finditer(masked):
        word = match.group()
        valid = (
            _word_at(masked, match.start()) == word
            and _is_capitalised(word)
            and not _is_alnum_at(masked, match.start() - 1)
        )
        joined = bool(run) and match.start() == previous_end + 1 and masked[previous_end] == " "
        if valid and joined:
            run.append(word)
        else:
            if run:
                runs.append(run)
            run = [word] if valid else []
        previous_end = match.end()
    if run:
        runs.append(run)
    return {" ".join(words) for words in runs if 2 <= len(words) <= 3}


def _scan_amounts_and_numbers(text: str) -> tuple[list[int | None], list[str]]:
    """Amounts (whole dollars, or None when not whole) and plain numbers outside amounts."""
    amounts: list[int | None] = []
    spans: list[tuple[int, int]] = []
    for match in _AMOUNT_RE.finditer(text):
        spans.append(match.span())
        number = match.group("n1") or match.group("n2")
        scale = (match.group("s1") or match.group("w1") or match.group("w2") or "").lower()
        dollars = Decimal(number.replace(",", "")) * _SCALES[scale]
        amounts.append(int(dollars) if dollars == dollars.to_integral_value() else None)
    numbers: list[str] = []
    for match in _NUMBER_RE.finditer(text):
        if any(start < match.end() and match.start() < end for start, end in spans):
            continue
        numbers.append(match.group("num"))
    return amounts, numbers


def _range_for(count: int) -> str | None:
    for label, low, high in HEADCOUNT_RANGES:
        if count >= low and (high is None or count <= high):
            return label
    return None


def _field_values(field: str, text: str, domain: str, name: str) -> set[object]:
    if field == "legal_name":
        return _legal_name_values(text, domain, name)
    if field == "hq_city":
        return _hq_city_values(text)
    if field == "ceo":
        return _ceo_values(text, domain, name)
    amounts, numbers = _scan_amounts_and_numbers(text)
    if field == "founded_year":
        years = (int(n) for n in numbers if _FOUR_DIGITS_RE.fullmatch(n))
        return {year for year in years if 1800 <= year <= 2099}
    if field == "headcount_range":
        counts = (int(n.replace(",", "")) for n in numbers if "." not in n)
        return {_range_for(count) for count in counts if count >= 1}
    if field == "funding_total":
        return {amount for amount in amounts if amount is not None}
    raise ValueError(f"unknown field: {field}")


def supported_values(domain: str, excerpt: str) -> dict[str, object]:
    """Field -> normalised value for every field the excerpt supports under A.2.

    The excerpt must be a single sentence that names the company, states a phrase
    for the field, contains no negating phrase, and whose values in the field's
    format all normalise to one value.
    """
    gated = _gate(domain, excerpt)
    if gated is None:
        return {}
    text, domain, name = gated
    supported: dict[str, object] = {}
    for field in FIELDS:
        if _STATEMENT_RE[field].search(text) is None:
            continue
        values = _field_values(field, text, domain, name)
        if len(values) == 1:
            supported[field] = next(iter(values))
    return supported


def _gate(domain: str, excerpt: str) -> tuple[str, str, str] | None:
    """The collapsed excerpt, lower-cased domain and company name when the excerpt is a single
    sentence that names the company and has no negating phrase (A.2); otherwise None."""
    text = _collapse(excerpt)
    if not text or split_sentences(text) != [text]:
        return None
    domain = domain.lower()
    name = company_name(domain)
    if _NEGATION_RE.search(text) or _word_re((domain, name)).search(text) is None:
        return None
    return text, domain, name


def supported_executives(domain: str, excerpt: str) -> dict[str, str]:
    """Title -> person's name for each title the excerpt supports (stage 3, `executives`).

    The same gate as ``supported_values`` applies. A title is supported when its phrase is
    in the excerpt and exactly one name of the ceo format follows it (A.4, A.5)."""
    gated = _gate(domain, excerpt)
    if gated is None:
        return {}
    text, domain, name = gated
    supported: dict[str, str] = {}
    for title in TITLES:
        phrase_re = _word_re(TITLE_PHRASES[title])
        if phrase_re.search(text) is None:
            continue
        names = _person_values(text, domain, name, phrase_re)
        if len(names) == 1:
            supported[title] = next(iter(names))
    return supported


@dataclass(frozen=True)
class Support:
    """One excerpt of prose that supports one value of one field."""

    field: str
    value: object
    excerpt: str


def extract_supports(domain: str, prose: str) -> list[Support]:
    """Every (field, value, excerpt) that a sentence of the prose supports.

    Sentences longer than 500 characters are not citable and are left out.
    """
    supports: list[Support] = []
    for sentence in prose_sentences(prose):
        if len(sentence) > MAX_EXCERPT_LENGTH:
            continue
        for field, value in supported_values(domain, sentence).items():
            supports.append(Support(field, value, sentence))
    return supports
