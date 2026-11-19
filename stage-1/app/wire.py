"""JSON and RFC 3339 helpers shared by every endpoint (§3.5).

Timestamps are `Moment`s: exact nanoseconds since the Unix epoch plus the display offset.
Comparisons use the nanoseconds, so fractional seconds of any RFC 3339 precision order
correctly. Output is whole seconds with the explicit offset.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .errors import malformed, validation

_RFC3339 = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?"
    r"(?:([Zz])|([+-])(\d{2}):(\d{2}))"
)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_NS = 10**9


@dataclass(frozen=True)
class Moment:
    ns: int  # nanoseconds since the Unix epoch
    offset: timedelta  # the offset the timestamp was written with


def parse_rfc3339(value: Any) -> Moment | None:
    """Parse an RFC 3339 timestamp that carries an explicit offset; None if invalid."""
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
        instant = datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=timezone(offset)
        )
    except ValueError:
        return None
    whole_seconds = (instant - _EPOCH) // timedelta(seconds=1)
    fraction_ns = int((fraction or "").ljust(9, "0"))
    return Moment(whole_seconds * _NS + fraction_ns, offset)


def format_ts(moment: Moment) -> str:
    """RFC 3339 with the explicit offset, to whole seconds."""
    local = datetime.fromtimestamp(moment.ns // _NS, tz=timezone(moment.offset))
    return local.isoformat(timespec="seconds")


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
