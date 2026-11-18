"""The service clock: follows system time until reset/clock calls fix it (§3.4)."""
import re
from datetime import datetime, timezone

from app.errors import invalid

_RFC3339 = re.compile(
    r"^\d{4}-\d\d-\d\d[Tt ]\d\d:\d\d:\d\d(\.\d+)?([Zz]|[+-]\d\d:\d\d)$")


def parse_timestamp(text: str) -> datetime:
    """RFC 3339 timestamp with an explicit offset, else 422 validation_failed."""
    if not _RFC3339.match(text):
        raise invalid("now must be an RFC 3339 timestamp with an offset")
    norm = text.replace("t", "T").replace(" ", "T")
    norm = norm[:-1] + "+00:00" if norm[-1] in "Zz" else norm
    if "." in norm:
        head, rest = norm.split(".", 1)
        digits = ""
        while rest and rest[0].isdigit():
            digits, rest = digits + rest[0], rest[1:]
        norm = f"{head}.{digits[:6].ljust(6, '0')}{rest}"
    try:
        value = datetime.fromisoformat(norm)
    except ValueError:
        raise invalid("now is not a valid timestamp")
    if value.tzinfo is None or value.utcoffset() is None:
        raise invalid("now needs an explicit offset")
    return value


class Clock:
    def __init__(self, fixed: datetime | None = None):
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed or datetime.now(timezone.utc)

    def set(self, value: datetime) -> None:
        self._fixed = value

    def advance(self, value: datetime) -> None:
        """Move the clock forward; a time before the current one is 422."""
        if value < self.now():
            raise invalid("now is earlier than the current clock time")
        self._fixed = value


def render(value: datetime) -> str:
    return value.isoformat()
