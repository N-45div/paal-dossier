"""Query-string parsing: first value wins, unknown parameters are ignored (spec 3.5)."""

import re
from urllib.parse import parse_qsl

from dossier.server.errors import validation

_DIGITS = re.compile(r"[0-9]+")


def parse_query(raw: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, value in parse_qsl(raw, keep_blank_values=True):
        values.setdefault(key, value)
    return values


def integer_param(value: str | None, default: int, low: int, high: int | None) -> int:
    """A plain decimal integer in range; an absent parameter takes the default."""
    if value is None:
        return default
    if _DIGITS.fullmatch(value) is None:
        raise validation("query parameter must be a plain decimal integer")
    number = int(value)
    if number < low or (high is not None and number > high):
        raise validation("query parameter is out of range")
    return number
