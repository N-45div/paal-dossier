"""Independent, specification-derived validator for a single cited excerpt."""
import re
from decimal import Decimal

SUFFIXES = ('Inc.', 'Corp.', 'LLC', 'LLP', 'L.P.', 'Ltd', 'Limited', 'Pty Ltd', 'plc', 'PLC', 'GmbH', 'AG', 'KG', 'SE', 'AS', 'A/S', 'ASA', 'AB', 'Oy', 'Oyj', 'B.V.', 'N.V.', 'S.A.', 'S.A.S.', 'S.L.', 'S.r.l.', 'S.p.A.', 's.r.o.', 'a.s.', 'K.K.')
PHRASES = {
    'legal_name': ('legal name', 'registered name', 'registered as', 'registered company', 'legal entity', 'name of record'),
    'hq_city': ('headquartered in', 'headquarters in', 'head office in', 'based in', 'registered office in', 'registered seat in'),
    'ceo': ('chief executive officer', 'chief executive', 'CEO'),
    'founded_year': ('founded', 'founding', 'established', 'incorporated'),
    'headcount_range': ('employs', 'employees', 'staff', 'people', 'headcount', 'workforce'),
    'funding_total': ('raised', 'funding', 'invested', 'investment'),
}
NEGATIONS = ('in talks to', 'plans to', 'planning to', 'wants to', 'expects to', 'hopes to', 'aims to', 'seeking', 'could', 'would', 'might', 'reportedly', 'rumoured', 'former', 'formerly', 'will become', 'not')
BOUNDARY_L = r'(?<![^\W_])'
BOUNDARY_R = r'(?![^\W_])'
NUMBER = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
NUM_GUARD_L = r'(?<!\w)(?<!\d,)(?<!\d\.)'
NUM_GUARD_R = r'(?!\w)(?![,.]\d)'
AMOUNT = re.compile(BOUNDARY_L + r'(?:US\$|USD|\$) ?(' + NUMBER + r')(?![,.]\d)(?: (thousand|million|billion)|(?i:(k|mn|m|bn)))?' + BOUNDARY_R + r'|' + BOUNDARY_L + r'(' + NUMBER + r')(?![,.]\d)(?: (thousand|million|billion))? (?:US )?dollars' + BOUNDARY_R, re.I)
NUMBERS = re.compile(NUM_GUARD_L + NUMBER + NUM_GUARD_R)
WORD = re.compile(BOUNDARY_L + r'[^\W\d_]+' + BOUNDARY_R, re.UNICODE)


def norm(text):
    return ' '.join(text.split())


def phrase(text, word):
    return re.search(BOUNDARY_L + re.escape(word) + BOUNDARY_R, text, re.I)


def prose(text):
    lines = text.splitlines()
    if lines and re.match(r'^[A-Z][a-z]*(?:-[A-Z][a-z]*)*: ', lines[0]):
        try:
            return '\n'.join(lines[lines.index('') + 1:])
        except ValueError:
            return ''
    return text


def sentences(text):
    result = []
    for line in text.splitlines():
        start = 0
        for match in re.finditer(r'[.!?]["”’)]*(?=\s)', line):
            end = match.end()
            prefix = line[start:end]
            if line[match.start()] == '.' and any(re.search(BOUNDARY_L + re.escape(s) + r'$' , prefix.rstrip('"”’' + ')')) for s in SUFFIXES if s.endswith('.')):
                continue
            value = prefix.strip()
            if value:
                result.append(value)
            start = end
        tail = line[start:].strip()
        if tail:
            result.append(tail)
    return result


def capital(word):
    return len(word) >= 2 and word[0].isupper() and word[1:].islower()


def upper(word):
    return len(word) >= 2 and word.isupper()


def amounts(text):
    values = []
    spans = []
    for match in AMOUNT.finditer(text):
        number = match.group(1) or match.group(4)
        scale = (match.group(2) or match.group(3) or match.group(5) or '').lower()
        factor = {'k': 1000, 'thousand': 1000, 'm': 1000000, 'mn': 1000000, 'million': 1000000, 'bn': 1000000000, 'billion': 1000000000}.get(scale, 1)
        result = Decimal(number.replace(',', '')) * factor
        spans.append(match.span())
        if result == int(result):
            values.append(int(result))
    return values, spans


def values_for(field, text, company, domain):
    if field == 'funding_total':
        return amounts(text)[0]
    if field in ('founded_year', 'headcount_range'):
        _, spans = amounts(text)
        numbers = []
        for match in NUMBERS.finditer(text):
            if any(a <= match.start() and match.end() <= b for a, b in spans):
                continue
            raw = match.group()
            if field == 'founded_year':
                digits = raw.replace(',', '')
                if len(digits) == 4 and digits.isdigit() and 1800 <= int(digits) <= 2099:
                    numbers.append(int(digits))
            elif '.' not in raw and int(raw.replace(',', '')) > 0:
                n = int(raw.replace(',', ''))
                bounds = ((10, '1-10'), (50, '11-50'), (200, '51-200'), (500, '201-500'), (1000, '501-1000'), (5000, '1001-5000'), (10000, '5001-10000'))
                numbers.append(next((label for limit, label in bounds if n <= limit), '10001+'))
        return numbers
    if field == 'legal_name':
        found = []
        for candidate in (company, domain):
            for start in re.finditer(BOUNDARY_L + re.escape(candidate) + BOUNDARY_R, text, re.I):
                rest = text[start.end():]
                candidates = []
                for suffix in SUFFIXES:
                    m = re.match(r'((?: [^\W\d_]+)*),? ' + re.escape(suffix) + BOUNDARY_R, rest)
                    if not m:
                        continue
                    words = m.group(1).split()
                    if all(capital(w) or upper(w) for w in words):
                        candidates.append(text[start.start():start.end() + m.end()])
                if candidates:
                    found.append(min(candidates, key=len))
        return found
    if field == 'hq_city':
        found = []
        for p in PHRASES[field]:
            for m in re.finditer(BOUNDARY_L + re.escape(p) + BOUNDARY_R + ' ', text, re.I):
                remaining = text[m.end():]
                words = list(WORD.finditer(remaining))
                if not words or words[0].start() != 0 or not capital(words[0].group()):
                    continue
                end = words[0].end()
                for w in words[1:]:
                    if remaining[end:w.start()] not in (' ', '-') or not capital(w.group()):
                        break
                    end = w.end()
                found.append(remaining[:end])
        return found
    if field == 'ceo':
        masked = text
        for p in sorted((company, domain, *PHRASES[field]), key=len, reverse=True):
            masked = re.sub(BOUNDARY_L + re.escape(p) + BOUNDARY_R, lambda m: '|' * len(m.group()), masked, flags=re.I)
        words = list(WORD.finditer(masked))
        runs = []
        current = []
        for word in words:
            if capital(word.group()):
                if current and masked[current[-1].end():word.start()] != ' ':
                    runs.append(current)
                    current = []
                current.append(word)
            elif current:
                runs.append(current)
                current = []
        if current:
            runs.append(current)
        return [masked[run[0].start():run[-1].end()] for run in runs if 2 <= len(run) <= 3]
    raise ValueError(field)


def supports(domain, field, value, excerpt):
    excerpt = norm(excerpt)
    if len(sentences(excerpt)) != 1:
        return False
    company = domain.split('.')[0].replace('-', ' ')
    if not (phrase(excerpt, company) or phrase(excerpt, domain)):
        return False
    if not any(phrase(excerpt, p) for p in PHRASES[field]) or any(phrase(excerpt, p) for p in NEGATIONS):
        return False
    values = values_for(field, excerpt, company, domain)
    return bool(values) and all(v == value for v in values)
