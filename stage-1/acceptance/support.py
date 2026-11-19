"""Independent implementation of Appendix A for judging returned citations."""
import re
from decimal import Decimal

PHRASES = {
    "legal_name": ("legal name", "registered name", "registered as", "registered company", "legal entity", "name of record"),
    "hq_city": ("headquartered in", "headquarters in", "head office in", "based in", "registered office in", "registered seat in"),
    "ceo": ("chief executive officer", "chief executive", "CEO"),
    "founded_year": ("founded", "founding", "established", "incorporated"),
    "headcount_range": ("employs", "employees", "staff", "people", "headcount", "workforce"),
    "funding_total": ("raised", "funding", "invested", "investment"),
}
NEGATIVE = ("in talks to", "plans to", "planning to", "wants to", "expects to", "hopes to", "aims to", "seeking", "could", "would", "might", "reportedly", "rumoured", "former", "formerly", "will become", "not")
SUFFIXES = ("Inc.", "Corp.", "LLC", "LLP", "L.P.", "Ltd", "Limited", "Pty Ltd", "plc", "PLC", "GmbH", "AG", "KG", "SE", "AS", "A/S", "ASA", "AB", "Oy", "Oyj", "B.V.", "N.V.", "S.A.", "S.A.S.", "S.L.", "S.r.l.", "S.p.A.", "s.r.o.", "a.s.", "K.K.")
NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
AMOUNT = re.compile(r"(?<![^\W_])(?:\$|US\$|USD) ?(?P<n1>" + NUMBER + r")(?: ?(?P<s1>thousand|million|billion)|(?P<a1>bn|mn|k|m))?(?![^\W_])|(?<![^\W_])(?P<n2>" + NUMBER + r")(?: (?P<s2>thousand|million|billion))? (?:US )?dollars(?![^\W_])", re.I)
NUMBERS = re.compile(r"(?<![\w,.])" + NUMBER + r"(?!\w|,\d|\.\d)", re.UNICODE)
WORDS = r"[^\W\d_]+"
TOKEN = re.compile(WORDS, re.UNICODE)


def whole(text, phrase):
    return re.search(r"(?<![^\W_])" + re.escape(phrase) + r"(?![^\W_])", text, re.I) is not None


def capital(word):
    return len(word) >= 2 and word[0].isupper() and word[1:].islower()


def single_sentence(text):
    text = " ".join(text.split())
    for m in re.finditer(r"[.!?][\"”’)]*(?=\s)", text):
        at = m.start()
        if text[at] == "." and any(text[:at + 1].endswith(s) and (at + 1 == len(s) or not text[at - len(s)].isalnum()) for s in SUFFIXES):
            continue
        return False
    return bool(text)


def amount_values(text):
    values, spans = [], []
    scale = {None: 1, "k": 1000, "thousand": 1000, "m": 1000000, "mn": 1000000, "million": 1000000, "bn": 1000000000, "billion": 1000000000}
    for m in AMOUNT.finditer(text):
        n = m.group("n1") or m.group("n2")
        s = m.group("s1") or m.group("a1") or m.group("s2")
        value = Decimal(n.replace(",", "")) * scale[s.lower() if s else None]
        spans.append(m.span())
        if value == value.to_integral_value():
            values.append(int(value))
    return values, spans


def values(text, domain, field):
    name = domain.split(".")[0].replace("-", " ")
    if field == "funding_total":
        return amount_values(text)[0]
    if field in ("founded_year", "headcount_range"):
        _, amounts = amount_values(text)
        result = []
        for m in NUMBERS.finditer(text):
            if any(start <= m.start() and m.end() <= end for start, end in amounts):
                continue
            raw = m.group().replace(",", "")
            if field == "founded_year":
                if len(raw) == 4 and raw.isdigit() and 1800 <= int(raw) <= 2099:
                    result.append(int(raw))
            elif raw.isdigit() and int(raw) >= 1:
                n = int(raw)
                result.append(next(label for hi, label in [(10, "1-10"), (50, "11-50"), (200, "51-200"), (500, "201-500"), (1000, "501-1000"), (5000, "1001-5000"), (10000, "5001-10000"), (float("inf"), "10001+")] if n <= hi))
        return result
    if field == "hq_city":
        result = []
        for phrase in PHRASES[field]:
            for m in re.finditer(r"(?<![^\W_])" + re.escape(phrase) + r" (" + WORDS + r"(?:[ -]" + WORDS + r")*)", text, re.I):
                words = re.split(r"[ -]", m.group(1))
                valid = []
                for word in words:
                    if not capital(word):
                        break
                    valid.append(word)
                if valid:
                    end = m.start(1) + len(valid[0])
                    for word in valid[1:]:
                        end += 1 + len(word)
                    result.append(text[m.start(1):end])
        return result
    if field == "ceo":
        work = text
        for phrase in sorted((domain, name, *PHRASES[field]), key=len, reverse=True):
            work = re.sub(r"(?<![^\W_])" + re.escape(phrase) + r"(?![^\W_])", "|", work, flags=re.I)
        result = []
        for match in re.finditer(WORDS + r"(?: " + WORDS + r")*", work):
            run = []
            for word in match.group().split(" ") + [""]:
                if capital(word):
                    run.append(word)
                else:
                    if 2 <= len(run) <= 3:
                        result.append(" ".join(run))
                    run = []
        return result
    result = []
    for match in re.finditer(r"(?<![^\W_])(?:" + re.escape(name) + "|" + re.escape(domain) + r")(?![^\W_])", text, re.I):
        start, pos = match.start(), match.end()
        while True:
            for suffix in sorted(SUFFIXES, key=len):
                target = re.match(r",? " + re.escape(suffix) + r"(?![^\W_])", text[pos:])
                if target:
                    result.append(text[start:pos + target.end()])
                    break
            else:
                token = re.match(r" (" + WORDS + r")", text[pos:])
                if token and (capital(token.group(1)) or (len(token.group(1)) >= 2 and token.group(1).isupper())):
                    pos += token.end()
                    continue
            break
    return result


def supports(text, domain, field, value):
    text = " ".join(text.split())
    name = domain.split(".")[0].replace("-", " ")
    if not single_sentence(text) or not (whole(text, name) or whole(text, domain)):
        return False
    if not any(whole(text, p) for p in PHRASES[field]) or any(whole(text, p) for p in NEGATIVE):
        return False
    found = values(text, domain, field)
    return bool(found) and all(v == value for v in found)
