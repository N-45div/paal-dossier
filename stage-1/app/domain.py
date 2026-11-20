"""Domain normalisation and validation (§4, R1.35–R1.36).

Every domain the API takes, in a body or a path, passes through `normalise_domain`.
"""

import re

from .errors import validation

_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_MAX_TOTAL = 253


def normalise_domain(raw: str) -> str:
    """Normalise then validate: 422 validation_failed for anything that is not a host name."""
    domain = raw.strip().lower()
    if domain.endswith("."):
        domain = domain[:-1]
    if domain.startswith("www."):
        domain = domain[len("www."):]
    labels = domain.split(".")
    if len(labels) < 2 or len(domain) > _MAX_TOTAL:
        raise validation("domain must be a host name with two or more labels")
    for label in labels:
        if _LABEL.fullmatch(label) is None:
            raise validation("domain must be a host name with two or more labels")
    return domain
