"""Independent oracle for Dossier stage 1: Appendix A ("supports") and the
page/header/citation rules of section 4.

Written by the Prover from the specification text only (stage-1.md, sections 4
and Appendix A). It does not read or import any builder code, and it is not a
port of the shipped check files.

Ledger ids: R1.94-R1.111 (fields, evidence, citations), R1.112-R1.120 (pages,
headers), R1.257-R1.310 (Appendix A).
"""
from __future__ import annotations

import re
from decimal import Decimal

FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")

# R1.90 headcount ranges, R1.93 mapping of a number to the range that contains it.
HEADCOUNT_RANGES = [
    (1, 10, "1-10"),
    (11, 50, "11-50"),
    (51, 200, "51-200"),
    (201, 500, "201-500"),
    (501, 1000, "501-1000"),
    (1001, 5000, "1001-5000"),
    (5001, 10000, "5001-10000"),
    (10001, None, "10001+"),
]

# R1.301-R1.302 legal-form suffixes, exactly as written.
LEGAL_SUFFIXES = [
    "Inc.", "Corp.", "LLC", "LLP", "L.P.", "Ltd", "Limited", "Pty Ltd", "plc", "PLC",
    "GmbH", "AG", "KG", "SE", "AS", "A/S", "ASA", "AB", "Oy", "Oyj", "B.V.", "N.V.",
    "S.A.", "S.A.S.", "S.L.", "S.r.l.", "S.p.A.", "s.r.o.", "a.s.", "K.K.",
]
DOTTED_SUFFIXES = [s for s in LEGAL_SUFFIXES if s.endswith(".")]

# R1.279-R1.284 statement phrases.
STATEMENT = {
    "legal_name": ["legal name", "registered name", "registered as", "registered company",
                   "legal entity", "name of record"],
    "hq_city": ["headquartered in", "headquarters in", "head office in", "based in",
                "registered office in", "registered seat in"],
    "ceo": ["chief executive officer", "chief executive", "CEO"],
    "founded_year": ["founded", "founding", "established", "incorporated"],
    "headcount_range": ["employs", "employees", "staff", "people", "headcount", "workforce"],
    "funding_total": ["raised", "funding", "invested", "investment"],
}

# R1.286 negating phrases.
NEGATING = [
    "in talks to", "plans to", "planning to", "wants to", "expects to", "hopes to",
    "aims to", "seeking", "could", "would", "might", "reportedly", "rumoured", "former",
    "formerly", "will become", "not",
]

_ALNUM = r"[^\W_]"  # a letter or a digit
_TOKEN = re.compile(r"[^\W_]+")  # maximal run of letters and digits
_HEADER_LINE = re.compile(r"^([A-Z][a-z]+(?:-[A-Z][a-z]+)*):(?: |$)")
_SCALE = {"k": 1000, "thousand": 1000, "m": 10**6, "mn": 10**6, "million": 10**6,
          "bn": 10**9, "billion": 10**9}
_NUM = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"

# R1.292-R1.294: a number, not joined to letters or digits by , or . in any other way.
_NUMBER = re.compile(
    r"(?<!" + _ALNUM + r")(?<!\d[.,])" + _NUM + r"(?!" + _ALNUM + r")(?![.,]\d)"
)
# R1.303-R1.306: amounts.
_AMOUNT = re.compile(
    r"(?<!" + _ALNUM + r")"
    r"(?:(?:US\$|\$|USD ?)(?P<n1>" + _NUM + r")(?P<s1>k|mn|m|bn| thousand| million| billion)?"
    r"|(?P<n2>" + _NUM + r")(?: (?P<s2>thousand|million|billion))? (?:US )?dollars)"
    r"(?!" + _ALNUM + r")",
    re.IGNORECASE,
)


def collapse(text: str) -> str:
    """Every run of whitespace written as one space, stripped (A.2 excerpt rule)."""
    return re.sub(r"\s+", " ", text).strip()


def _phrase_pattern(phrase: str) -> re.Pattern:
    """Whole-word, case-insensitive; a space in the phrase matches one space (A.2)."""
    body = " ".join(re.escape(w) for w in phrase.split(" "))
    return re.compile(r"(?<!" + _ALNUM + r")" + body + r"(?!" + _ALNUM + r")", re.IGNORECASE)


def _company_pattern(domain: str) -> re.Pattern:
    """The company's name (first label, '-' read as a space) or its domain (A.2 item 2)."""
    name = domain.split(".")[0].replace("-", " ")
    name_body = " ".join(re.escape(w) for w in name.split(" "))
    alts = [name_body, re.escape(domain)]
    return re.compile(
        r"(?<!" + _ALNUM + r")(?:" + "|".join(alts) + r")(?!" + _ALNUM + r")", re.IGNORECASE
    )


def _is_alnum(ch: str) -> bool:
    return ch.isalnum()


def _is_cap(tok: str) -> bool:
    """Capitalised word (A.4): an uppercase letter followed by one or more lowercase letters."""
    return tok.isalpha() and len(tok) >= 2 and tok[0].isupper() and tok[1:].islower()


def _is_upper(tok: str) -> bool:
    """Uppercase word (A.4): two or more uppercase letters."""
    return tok.isalpha() and len(tok) >= 2 and tok.isupper()


def _ends_with_suffix(text: str, i: int) -> bool:
    """True when the '.' at text[i] ends a legal-form suffix written as a whole word (A.1)."""
    head = text[: i + 1]
    for suf in DOTTED_SUFFIXES:
        if head.endswith(suf):
            start = len(head) - len(suf)
            if start == 0 or not _is_alnum(text[start - 1]):
                return True
    return False


def split_sentences(text: str) -> list[str]:
    """A.1: split one line of prose into sentences."""
    out: list[str] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ".!?":
            j = i + 1
            while j < n and text[j] in '"”’)':
                j += 1
            if j < n and text[j].isspace() and not (ch == "." and _ends_with_suffix(text, i)):
                seg = text[start:j].strip()
                if seg:
                    out.append(seg)
                start = j
                i = j
                continue
        i += 1
    seg = text[start:].strip()
    if seg:
        out.append(seg)
    return out


def prose_sentences(prose: str) -> list[str]:
    """A.1: split prose at each line break, then each line into sentences."""
    out: list[str] = []
    for line in prose.split("\n"):
        out.extend(split_sentences(line))
    return out


# ---- value extraction (A.4) -------------------------------------------------

def _legal_values(domain: str, s: str) -> list[str]:
    values: list[str] = []
    for m in _company_pattern(domain).finditer(s):
        ends: list[int] = []
        p = m.end()
        while True:
            for sep in (", ", " "):
                if s.startswith(sep, p):
                    q = p + len(sep)
                    for suf in LEGAL_SUFFIXES:
                        if s.startswith(suf, q):
                            e = q + len(suf)
                            if e == len(s) or not _is_alnum(s[e]):
                                ends.append(e)
            # zero or more capitalised or uppercase words, each after one space
            if s.startswith(" ", p):
                tok = _TOKEN.match(s, p + 1)
                if tok and (_is_cap(tok.group()) or _is_upper(tok.group())):
                    p = tok.end()
                    continue
            break
        if ends:
            values.append(s[m.start(): min(ends)])
    return values


def _cap_run_end(s: str, q: int) -> int | None:
    tok = _TOKEN.match(s, q)
    if not tok or not _is_cap(tok.group()):
        return None
    end = tok.end()
    while end < len(s) and s[end] in " -":
        nxt = _TOKEN.match(s, end + 1)
        if nxt and _is_cap(nxt.group()):
            end = nxt.end()
        else:
            break
    return end


def _hq_values(s: str) -> list[str]:
    out: list[str] = []
    for ph in STATEMENT["hq_city"]:
        for m in _phrase_pattern(ph).finditer(s):
            p = m.end()
            if s.startswith(" ", p):
                q = p + 1
                e = _cap_run_end(s, q)
                if e is not None:
                    out.append(s[q:e])
    return out


def _ceo_values(domain: str, s: str) -> list[str]:
    t = _company_pattern(domain).sub(" | ", s)
    for ph in STATEMENT["ceo"]:
        t = _phrase_pattern(ph).sub(" | ", t)
    groups: list[list[str]] = []
    cur: list[str] = []
    prev_end: int | None = None
    for tok in _TOKEN.finditer(t):
        w = tok.group()
        if not _is_cap(w):
            if cur:
                groups.append(cur)
            cur = []
            prev_end = None
            continue
        if cur and prev_end is not None and t[prev_end: tok.start()] == " ":
            cur.append(w)
        else:
            if cur:
                groups.append(cur)
            cur = [w]
        prev_end = tok.end()
    if cur:
        groups.append(cur)
    return [" ".join(g) for g in groups if 2 <= len(g) <= 3]


def _amount_spans(s: str) -> list[tuple[int, int, int | None]]:
    spans = []
    for m in _AMOUNT.finditer(s):
        num = m.group("n1") or m.group("n2")
        scale_txt = (m.group("s1") or m.group("s2") or "").strip().lower()
        scale = _SCALE.get(scale_txt, 1)
        val = Decimal(num.replace(",", "")) * scale
        whole = int(val) if val == val.to_integral_value() else None
        spans.append((m.start(), m.end(), whole))
    return spans


def _numbers_outside_amounts(s: str):
    spans = _amount_spans(s)
    for m in _NUMBER.finditer(s):
        if any(m.start() < se and m.end() > ss for ss, se, _ in spans):
            continue
        yield m.group()


def _founded_values(s: str) -> list[int]:
    out = []
    for txt in _numbers_outside_amounts(s):
        if re.fullmatch(r"\d{4}", txt) and 1800 <= int(txt) <= 2099:
            out.append(int(txt))
    return out


def _headcount_values(s: str) -> list[str]:
    out = []
    for txt in _numbers_outside_amounts(s):
        if "." in txt:
            continue
        n = int(txt.replace(",", ""))
        if n < 1:
            continue
        for lo, hi, label in HEADCOUNT_RANGES:
            if n >= lo and (hi is None or n <= hi):
                out.append(label)
                break
    return out


def _funding_values(s: str) -> list[int]:
    return [v for _, _, v in _amount_spans(s) if v is not None]


def _values(field: str, domain: str, s: str) -> list:
    if field == "legal_name":
        return _legal_values(domain, s)
    if field == "hq_city":
        return _hq_values(s)
    if field == "ceo":
        return _ceo_values(domain, s)
    if field == "founded_year":
        return _founded_values(s)
    if field == "headcount_range":
        return _headcount_values(s)
    if field == "funding_total":
        return _funding_values(s)
    raise KeyError(field)


def names_company(domain: str, excerpt: str) -> bool:
    return bool(_company_pattern(domain).search(collapse(excerpt)))


def supported_values(domain: str, excerpt: str) -> dict:
    """Appendix A.2: every field this single excerpt supports for the company, mapped to
    the normalised value (A.5). A field the excerpt does not support is absent."""
    s = collapse(excerpt)
    if len(split_sentences(s)) != 1:  # item 1: a single sentence
        return {}
    if not _company_pattern(domain).search(s):  # item 2: names the company
        return {}
    if any(_phrase_pattern(p).search(s) for p in NEGATING):  # item 4
        return {}
    out: dict = {}
    for field in FIELDS:
        if not any(_phrase_pattern(p).search(s) for p in STATEMENT[field]):  # item 3
            continue
        vals = _values(field, domain, s)  # item 5
        if vals and all(v == vals[0] for v in vals):
            out[field] = vals[0]
    return out


def supports(domain: str, excerpt: str, field: str, value) -> bool:
    return supported_values(domain, excerpt).get(field, object()) == value


# ---- pages, headers, citations (section 4) ----------------------------------

def split_header(text: str) -> tuple[dict, str]:
    """R1.113-R1.116: header lines end at the first empty line; the rest is prose.
    A text whose first line is not a header line is all prose."""
    lines = text.split("\n")
    if not lines or not _HEADER_LINE.match(lines[0]):
        return {}, text
    headers: dict = {}
    i = 0
    while i < len(lines) and lines[i] != "":
        m = _HEADER_LINE.match(lines[i])
        if m:
            headers[m.group(1)] = lines[i][m.end():]
        i += 1
    prose = "\n".join(lines[i + 1:]) if i < len(lines) else ""
    return headers, prose


def excerpt_in_prose(prose: str, excerpt: str) -> bool:
    """R1.104-R1.105: copied from the prose, whitespace runs may be one space, 1-500 chars."""
    if not (1 <= len(excerpt) <= 500):
        return False
    return collapse(excerpt) in collapse(prose)
