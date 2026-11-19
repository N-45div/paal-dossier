"""RFC 3339 parsing and printing with an explicit offset (spec 3.5, RL1.6, RL1.9)."""

import re
from datetime import datetime

_RFC3339 = re.compile(
    r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})"
)


def parse_rfc3339(text: str) -> datetime | None:
    """Return an aware datetime, or None when the text is not RFC 3339 with an offset."""
    if not _RFC3339.fullmatch(text):
        return None
    normalised = text[:10] + "T" + text[11:]
    if normalised.endswith(("Z", "z")):
        normalised = normalised[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def format_timestamp(instant: datetime) -> str:
    """Print an instant in the offset it was set with, e.g. 2026-09-24T19:00:00+02:00."""
    return instant.isoformat()
