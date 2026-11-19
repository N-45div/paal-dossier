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
        if second == "60":
            # RL26: a leap second is valid only where the UTC instant is 23:59:60; it orders as the
            # instant one second after 23:59:59 UTC.
            wall = datetime(
                int(year), int(month), int(day), int(hour), int(minute), 59, tzinfo=timezone(offset)
            )
            utc = wall.astimezone(timezone.utc)
            if (utc.hour, utc.minute) != (23, 59):
                return None
            whole = (utc - _EPOCH) // timedelta(seconds=1) + 1
        else:
            instant = datetime(
                int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=timezone(offset)
            )
            whole = (instant - _EPOCH) // timedelta(seconds=1)
    except ValueError:
        return None
    digits = fraction or ""
    exact = Fraction(whole) + (Fraction(Decimal("0." + digits)) if digits else Fraction(0))
    return Moment(exact, digits.rstrip("0"), offset)


def format_ts(moment: Moment) -> str:
    """RFC 3339 with the explicit offset; the fraction is printed as the clock holds it."""
    seconds = math.floor(moment.at)
    local = datetime.fromtimestamp(seconds, tz=timezone(moment.offset)).isoformat(timespec="seconds")
    if not moment.frac:
        return local
    return local[:19] + "." + moment.frac + local[19:]


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
