"""Independent Stage 2 candidate ranking and field invariants (R2.31–R2.49)."""
from datetime import date
from decimal import Decimal
from functools import cmp_to_key
import re

_STAMP = re.compile(
    r'^(\d{4})-(\d\d)-(\d\d)[Tt](\d\d):(\d\d):(\d\d)'
    r'(?:\.([0-9]+))?([Zz]|[+-]\d\d:\d\d)$', re.ASCII)
_AUTHORITY = {'own': 2, 'filing': 2, 'news': 1, 'aggregator': 0, None: 0}
_PROVIDER = {'nimble': 0, 'tavily': 1, 'kernel': 2, 'browserbase': 3}


def instant(text):
    """Comparable UTC instant, retaining all written fractional digits."""
    match = _STAMP.fullmatch(text)
    if not match:
        raise ValueError('not RFC 3339')
    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    if hour > 23 or minute > 59 or second > 60:
        raise ValueError('invalid clock time')
    ordinal = date(year, month, day).toordinal()
    zone = match.group(8)
    offset = 0
    if zone not in ('Z', 'z'):
        zh, zm = int(zone[1:3]), int(zone[4:6])
        if zh > 23 or zm > 59:
            raise ValueError('invalid offset')
        offset = (zh * 60 + zm) * 60 * (1 if zone[0] == '+' else -1)
    whole = ordinal * 86400 + hour * 3600 + minute * 60 + second - offset
    minimum = date(1, 1, 1).toordinal() * 86400
    maximum = date(9999, 12, 31).toordinal() * 86400 + 86399
    if second == 60:
        # RL70: :60 is valid only when the corresponding UTC :59 is 23:59:59.
        # The leap second sorts one second after that UTC second.
        before_leap = whole - 1
        if before_leap % 86400 != 86399 or not minimum <= before_leap <= maximum:
            raise ValueError('leap second is not at UTC 23:59:60')
    elif not minimum <= whole <= maximum:
        raise ValueError('instant outside supported UTC range')
    fraction = Decimal('0.' + (match.group(7) or '0'))
    return whole, fraction


def normal_value(value):
    return value.strip() if isinstance(value, str) else value


def _compare(left, right):
    def compare(a, b):
        return (a > b) - (a < b)
    rank = compare(_AUTHORITY[right['kind']], _AUTHORITY[left['kind']])
    if rank:
        return rank
    a, b = left['published_at'], right['published_at']
    if a is None or b is None:
        rank = compare(a is None, b is None)
    else:
        rank = compare(instant(b), instant(a))
    if rank:
        return rank
    return (compare(left['url'], right['url']) or
            compare(_PROVIDER[left['provider']], _PROVIDER[right['provider']]) or
            compare(normal_value(left['value']), normal_value(right['value'])))


def ranked(candidates):
    return sorted(candidates, key=cmp_to_key(_compare))


def assert_field(field):
    """Compare public field structure to selection, independently of the service."""
    candidates = field['candidates']
    assert candidates == ranked(candidates), 'candidates not in selection order'
    assert all(type(c['selected']) is bool for c in candidates)
    assert [c['selected'] for c in candidates] == ([True] + [False] * (len(candidates) - 1) if candidates else [])
    if not candidates:
        assert field['value'] is None and field['status'] == 'unknown' and field['citations'] == []
        return
    value = normal_value(candidates[0]['value'])
    distinct = {(type(normal_value(c['value'])), normal_value(c['value'])) for c in candidates}
    assert normal_value(field['value']) == value
    assert field['status'] == ('known' if len(distinct) == 1 else 'contested')
    citations = [{k: c[k] for k in ('url', 'excerpt', 'provider')}
                 for c in candidates if normal_value(c['value']) == value]
    assert field['citations'] == citations
