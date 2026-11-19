"""Domain normalisation shared by every endpoint that takes a domain (§4)."""
from __future__ import annotations

import re

_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOST = re.compile(rf"{_LABEL}(?:\.{_LABEL})+")


class InvalidDomain(ValueError):
    """The text is not a valid host name after normalisation."""


def normalise_domain(raw: str) -> str:
    """Strip, lowercase, drop one trailing '.' and one leading 'www.'; validate the host name."""
    text = raw.strip().lower()
    if text.endswith("."):
        text = text[:-1]
    if text.startswith("www."):
        text = text[4:]
    if len(text) > 253 or _HOST.fullmatch(text) is None:
        raise InvalidDomain(raw)
    return text
