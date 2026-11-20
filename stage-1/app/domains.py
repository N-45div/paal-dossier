"""Domain normalisation (spec §4): every domain in a body or path passes through here."""

from __future__ import annotations

import re

from .errors import validation_failed

_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
MAX_DOMAIN_LENGTH = 253


def normalise_domain(raw: str) -> str:
    """Trim, lowercase, drop one trailing `.` and one leading `www.`; then validate the host."""
    domain = raw.strip().lower()
    if domain.endswith("."):
        domain = domain[:-1]
    if domain.startswith("www."):
        domain = domain[len("www."):]
    labels = domain.split(".")
    if (
        len(labels) < 2
        or len(domain) > MAX_DOMAIN_LENGTH
        or not all(_LABEL.fullmatch(label) for label in labels)
    ):
        raise validation_failed("domain must be a valid host name")
    return domain
