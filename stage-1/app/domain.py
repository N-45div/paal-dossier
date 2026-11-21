"""Domain normalisation (spec §4)."""

from __future__ import annotations

import re

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalise_domain(raw: str) -> str | None:
    """Return the normalised host name, or None when it is not a valid domain.

    Normalisation: trim whitespace, lowercase, drop one trailing '.', drop one leading 'www.'.
    The result must have two or more labels of 1..63 chars from [a-z0-9-] (no leading or
    trailing '-') and be at most 253 characters long.
    """
    domain = raw.strip().lower()
    if domain.endswith("."):
        domain = domain[:-1]
    if domain.startswith("www."):
        domain = domain[4:]
    if len(domain) > 253:
        return None
    labels = domain.split(".")
    if len(labels) < 2:
        return None
    if not all(_LABEL.match(label) for label in labels):
        return None
    return domain
