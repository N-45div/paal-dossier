"""Domain normalisation and host-name validation (spec section 4)."""

import re

_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?|[a-z0-9]")


def normalise(raw: str) -> str:
    """Strip whitespace, lowercase, drop one trailing dot and one leading www."""
    domain = raw.strip().lower()
    if domain.endswith("."):
        domain = domain[:-1]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def is_valid_host(domain: str) -> bool:
    """Two or more labels, each 1 to 63 characters of a-z, 0-9, '-', no edge '-'; 253 max."""
    if len(domain) > 253:
        return False
    labels = domain.split(".")
    if len(labels) < 2:
        return False
    return all(_LABEL.fullmatch(label) for label in labels)
