"""RFC 3339 timestamps for stage 2 (RL66): the grammar and the instant they denote.

Separator T or t, zone designator Z or z, and an explicit numeric offset are required. A space
separator, date-only, no offset and basic form are refused. Fractions of any length are accepted.
Ranges are checked; a leap second (:60) is accepted. The engine must not import from app/, so
this module mirrors the grammar. Callers keep the timestamp text as written and use the instant
only for ordering.
"""

from __future__ import annotations

import datetime
import re
from decimal import Decimal
from typing import Optional

_RFC3339 = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})"
    r"[Tt](?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<fraction>\.\d+)?"
    r"(?P<zone>[Zz]|(?P<sign>[+-])(?P<off_hour>\d{2}):(?P<off_minute>\d{2}))"
)


def instant(value: Optional[str]) -> Optional[tuple]:
    """The exact instant of a valid RFC 3339 timestamp, else None.

    Returns (utc datetime to the whole second, Decimal fraction in [0, 1)). A leap second is
    one second after :59 of its minute. Tuples compare in instant order.
    """
    if not isinstance(value, str):
        return None
    match = _RFC3339.fullmatch(value)
    if match is None:
        return None
    parts = match.groupdict()
    try:
        day = datetime.date(int(parts["year"]), int(parts["month"]), int(parts["day"]))
    except ValueError:
        return None
    hour, minute, second = int(parts["hour"]), int(parts["minute"]), int(parts["second"])
    if hour > 23 or minute > 59 or second > 60:
        return None
    if parts["sign"] is not None:
        off_hour, off_minute = int(parts["off_hour"]), int(parts["off_minute"])
        if off_hour > 23 or off_minute > 59:
            return None
        offset = datetime.timedelta(hours=off_hour, minutes=off_minute)
        if parts["sign"] == "-":
            offset = -offset
        zone = datetime.timezone(offset)
    else:
        zone = datetime.timezone.utc
    leap = second == 60
    local = datetime.datetime(day.year, day.month, day.day, hour, minute, 59 if leap else second, tzinfo=zone)
    moment = local.astimezone(datetime.timezone.utc)
    if leap:
        moment += datetime.timedelta(seconds=1)
    fraction = Decimal("0" + parts["fraction"]) if parts["fraction"] else Decimal(0)
    return (moment, fraction)


def is_rfc3339(value: Optional[str]) -> bool:
    return instant(value) is not None
