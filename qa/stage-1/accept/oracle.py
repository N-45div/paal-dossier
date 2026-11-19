"""Appendix A evaluator, derived from the specification rather than service code."""
import re
from decimal import Decimal

FIELDS = ('legal_name', 'hq_city', 'ceo', 'founded_year', 'headcount_range', 'funding_total')
PHRASES = {
    'legal_name': ('legal name', 'registered name', 'registered as', 'registered company', 'legal entity', 'name of record'),
    'hq_city': ('headquartered in', 'headquarters in', 'head office in', 'based in', 'registered office in', 'registered seat in'),
    'ceo': ('chief executive officer', 'chief executive', 'CEO'),
    'founded_year': ('founded', 'founding', 'established', 'incorporated'),
    'headcount_range': ('employs', 'employees', 'staff', 'people', 'headcount', 'workforce'),
    'funding_total': ('raised', 'funding', 'invested', 'investment'),
}
NEGATIVE = ('in talks to', 'plans to', 'planning to', 'wants to', 'expects to', 'hopes to',
            'aims to', 'seeking', 'could', 'would', 'might', 'reportedly', 'rumoured',
            'former', 'formerly', 'will become', 'not')
SUFFIXES = ('Inc.', 'Corp.', 'LLC', 'LLP', 'L.P.', 'Ltd', 'Limited', 'Pty Ltd', 'plc',
            'PLC', 'GmbH', 'AG', 'KG', 'SE', 'AS', 'A/S', 'ASA', 'AB', 'Oy', 'Oyj',
            'B.V.', 'N.V.', 'S.A.', 'S.A.S.', 'S.L.', 'S.r.l.', 'S.p.A.', 's.r.o.', 'a.s.', 'K.K.')
NUM = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
NUMBER = re.compile(r'(?<![^\W_])(?<!\d[,.])' + NUM + r'(?![^\W_]|[,.]\d)')
AMOUNT = re.compile(r'(?<![^\W_])(?:(?:US\$|\$|USD) ?(' + NUM +
                    r')(?![,.]\d)(?:((?:mn|bn|k|m))(?![^\W_])| (thousand|million|billion)(?![^\W_]))?|('
                    + NUM + r')(?![,.]\d)(?: (thousand|million|billion))? (?:US )?dollars)(?![^\W_])', re.I)
WORD = r'[^\W\d_]+'
WORD_RUN = re.compile(r'(?<![^\W_])' + WORD + r'(?:[ -]' + WORD + r')*(?![^\W_])', re.UNICODE)


def boundary(text):
    return r'(?<![^\W_])' + re.escape(text) + r'(?![^\W_])'


def contains(text, phrases):
    return any(re.search(boundary(p), text, re.I) for p in phrases)


def sentences(text):
    out = []
    for line in text.splitlines():
        start = 0
        for m in re.finditer(r'[.!?]["”’)]*(?=\s)', line):
            end = m.end()
            if line[m.start()] == '.' and any(
                line[:m.start()+1].endswith(s) and
                (m.start()+1 == len(s) or not line[m.start()+1-len(s)-1].isalnum())
                for s in SUFFIXES if s.endswith('.')
            ):
                continue
            fragment = line[start:end].strip()
            if fragment:
                out.append(fragment)
            start = end
        tail = line[start:].strip()
        if tail:
            out.append(tail)
    return out


def prose(text):
    lines = text.splitlines()
    if lines and re.fullmatch(r'[A-Z][a-z]*(?:-[A-Z][a-z]*)*: .*', lines[0]):
        try:
            return '\n'.join(lines[lines.index('') + 1:])
        except ValueError:
            return ''
    return text


def amounts(text):
    found = []
    scale = {'k': 1000, 'thousand': 1000, 'm': 1000000, 'mn': 1000000,
             'million': 1000000, 'bn': 1000000000, 'billion': 1000000000}
    for match in AMOUNT.finditer(text):
        num = match.group(1) or match.group(4)
        suffix = (match.group(2) or match.group(3) or match.group(5) or '').lower()
        amount = Decimal(num.replace(',', '')) * scale.get(suffix, 1)
        if amount == amount.to_integral_value():
            found.append((match.span(), int(amount)))
        else:
            found.append((match.span(), None))
    return found


def capital(word):
    return len(word) >= 2 and word[0].isupper() and word[1:].islower()


def capital_runs(text, separators=' '):
    words = list(re.finditer(r'(?<![^\W_])' + WORD + r'(?![^\W_])', text))
    runs, run = [], []
    for word in words:
        if not capital(word.group()):
            if run:
                runs.append(run)
                run = []
            continue
        if run and text[run[-1].end():word.start()] not in separators:
            runs.append(run)
            run = []
        run.append(word)
    if run:
        runs.append(run)
    return runs


def candidates(domain, field, text):
    text = re.sub(r'\s+', ' ', text).strip()
    company = domain.split('.')[0].replace('-', ' ')
    if len(sentences(text)) != 1 or not contains(text, (company, domain)):
        return set()
    if not contains(text, PHRASES[field]) or contains(text, NEGATIVE):
        return set()
    values = []
    if field == 'legal_name':
        for match in re.finditer(boundary(company) + '|' + boundary(domain), text, re.I):
            rest = text[match.end():]
            options = []
            for suffix in SUFFIXES:
                expr = r'((?: ' + WORD + r')*),? ' + re.escape(suffix) + r'(?![^\W_])'
                m = re.match(expr, rest)
                if m and all(capital(w) or (len(w) >= 2 and w.isupper()) for w in m.group(1).split()):
                    options.append(m.end())
            if options:
                values.append(text[match.start():match.end() + min(options)])
    elif field == 'hq_city':
        for phrase in PHRASES[field]:
            for match in re.finditer(boundary(phrase) + ' ', text, re.I):
                for run in capital_runs(text, (' ', '-')):
                    if run[0].start() == match.end():
                        values.append(text[run[0].start():run[-1].end()])
    elif field == 'ceo':
        redacted = text
        for term in (company, domain, *PHRASES['ceo']):
            redacted = re.sub(boundary(term), ' | ', redacted, flags=re.I)
        for run in capital_runs(redacted, (' ',)):
            if 2 <= len(run) <= 3:
                values.append(redacted[run[0].start():run[-1].end()])
    elif field == 'funding_total':
        values = [value for _, value in amounts(text) if value is not None]
    else:
        amount_spans = [span for span, _ in amounts(text)]
        for match in NUMBER.finditer(text):
            if any(match.start() < end and match.end() > start for start, end in amount_spans):
                continue
            raw = match.group()
            if field == 'founded_year' and re.fullmatch(r'\d{4}', raw) and 1800 <= int(raw) <= 2099:
                values.append(int(raw))
            if field == 'headcount_range' and '.' not in raw and int(raw.replace(',', '')) >= 1:
                number = int(raw.replace(',', ''))
                bounds = ((10,'1-10'), (50,'11-50'), (200,'51-200'), (500,'201-500'),
                          (1000,'501-1000'), (5000,'1001-5000'), (10000,'5001-10000'), (float('inf'),'10001+'))
                values.append(next(label for maximum, label in bounds if number <= maximum))
    return set(values) if len(set(values)) == 1 else set()


def corpus_candidates(domain, pages):
    answer = {field: set() for field in FIELDS}
    for page in pages:
        for sentence in sentences(page['text']):
            if len(sentence) <= 500:
                for field in FIELDS:
                    answer[field].update(candidates(domain, field, sentence))
    return answer
