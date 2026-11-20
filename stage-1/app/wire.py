"""JSON and RFC 3339 helpers shared by every endpoint (§3.5).

Timestamps are `Moment`s: an exact Fraction of seconds since the Unix epoch, the fraction
digits as written, and the display offset. Comparisons are exact at any fraction precision.
"""

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from typing import Any

from .errors import malformed, validation

_RFC3339 = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?"
    r"(?:([Zz])|([+-])(\d{2}):(\d{2}))"
)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Moment:
    at: Fraction  # exact seconds since the Unix epoch, any fraction precision
    frac: str  # the fraction digits as written, trailing zeros removed ("" for none)
    offset: timedelta  # the offset the timestamp was written with


def parse_rfc3339(value: Any) -> Moment | None:
    """Parse an RFC 3339 timestamp with an explicit offset (Z or ±HH:MM); None if invalid.

    The separator is T or t, the zone designator Z or z. Fractions of any length are exact.
    """
    if not isinstance(value, str):
        return None
    match = _RFC3339.fullmatch(value)
    if match is None:
        return None
    year, month, day, hour, minute, second, fraction, zulu, sign, off_h, off_m = match.groups()
    if zulu:
        offset = timedelta(0)
    else:
        off_h_i, off_m_i = int(off_h), int(off_m)
        if off_h_i > 23 or off_m_i > 59:
            return None
        offset = timedelta(hours=off_h_i, minutes=off_m_i) * (1 if sign == "+" else -1)
    try:
        instant_check = datetime(
            int(year), int(month), int(day), int(hour), int(minute), min(int(second), 59), tzinfo=timezone(offset)
        )
        instant_check.astimezone(timezone.utc)  # raises OverflowError when the UTC instant leaves 0001-9999
        if second == "60":
            # RL26: a leap second is valid only where the UTC instant is 23:59:60; it orders as the
            # instant one second after 23:59:59 UTC.
            wall = datetime(
                int(year), int(month), int(day), int(hour), int(minute), 59, tzinfo=timezone(offset)
            )
            utc = wall.astimezone(timezone.utc)
            if (utc.hour, utc.minute) != (23, 59):
                return None
            # The leap instant is the second after 23:59:59 UTC; it must itself lie in years 0001-9999.
            leap_instant = utc + timedelta(seconds=1)  # raises OverflowError past 9999-12-31T23:59:59
            whole = (leap_instant - _EPOCH) // timedelta(seconds=1)
        else:
            instant = datetime(
                int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=timezone(offset)
            )
            whole = (instant - _EPOCH) // timedelta(seconds=1)
    except (ValueError, OverflowError):
        return None
    digits = fraction or ""
    exact = Fraction(whole) + (Fraction(Decimal("0." + digits)) if digits else Fraction(0))
    return Moment(exact, digits.rstrip("0"), offset)


def format_ts(moment: Moment) -> str:
    """RFC 3339 with the explicit offset; the fraction is printed as the clock holds it.

    The wall time is computed from the instant by civil-calendar arithmetic, so no value that
    parses can fail to format (year 0001 and 9999 at the offset limits included).
    """
    local_seconds = math.floor(moment.at) + int(moment.offset.total_seconds())
    year, month, day, hour, minute, second = _civil_from_seconds(local_seconds)
    sign = "+" if moment.offset >= timedelta(0) else "-"
    magnitude = abs(int(moment.offset.total_seconds())) // 60
    text = (
        f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
        f"{'.' + moment.frac if moment.frac else ''}"
        f"{sign}{magnitude // 60:02d}:{magnitude % 60:02d}"
    )
    return text


def _civil_from_seconds(seconds: int) -> tuple[int, int, int, int, int, int]:
    """Proleptic Gregorian date and time of day for seconds since 1970-01-01T00:00:00 (Hinnant)."""
    days, second_of_day = divmod(seconds, 86400)
    z = days + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    year = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    month = mp + 3 if mp < 10 else mp - 9
    if month <= 2:
        year += 1
    hour, rest = divmod(second_of_day, 3600)
    minute, second = divmod(rest, 60)
    return year, month, day, hour, minute, second


def parse_json(raw: bytes) -> Any:
    """Parse a request body; anything unparseable is 400 malformed_request."""
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise malformed("body is not valid JSON") from None


def encode_json(payload: Any) -> bytes:
    # ASCII escapes keep lone surrogates from accepted strings encodable (a valid JSON escape).
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def require_object(value: Any) -> dict:
    if not isinstance(value, dict):
        raise malformed("request body must be a JSON object")
    return value


def required_string(body: dict, key: str) -> str:
    """A required string field: missing is 422, a non-string is 400."""
    if key not in body:
        raise validation(f"{key} is required")
    value = body[key]
    if not isinstance(value, str):
        raise malformed(f"{key} must be a string")
    return value
