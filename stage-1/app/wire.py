"""JSON and RFC 3339 helpers shared by every endpoint (§3.5)."""

import json
import re
from datetime import datetime
from typing import Any

from .errors import malformed, validation

_RFC3339 = re.compile(
    r"(\d{4}-\d{2}-\d{2})[Tt ](\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|z|[+-]\d{2}:\d{2})"
)


def parse_rfc3339(value: Any) -> datetime | None:
    """Parse an RFC 3339 timestamp that carries an explicit offset; None if invalid."""
    if not isinstance(value, str):
        return None
    match = _RFC3339.fullmatch(value)
    if match is None:
        return None
    date, clock, fraction, offset = match.groups()
    if offset in ("Z", "z"):
        offset = "+00:00"
    text = f"{date}T{clock}"
    if fraction:
        text += "." + (fraction + "000000")[:6]
    text += offset
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def format_ts(moment: datetime) -> str:
    """Format a timestamp as RFC 3339 with its explicit offset, to whole seconds."""
    return moment.isoformat(timespec="seconds")


def parse_json(raw: bytes) -> Any:
    """Parse a request body; anything unparseable is 400 malformed_request."""
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise malformed("body is not valid JSON") from None


def encode_json(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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
