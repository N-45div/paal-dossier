"""Domain normalisation and validation (§4 Domains)."""
import re

from app.errors import invalid

_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def normalise(raw: str) -> str:
    domain = raw.strip().lower()
    if domain.endswith("."):
        domain = domain[:-1]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def is_valid(domain: str) -> bool:
    if len(domain) > 253:
        return False
    labels = domain.split(".")
    return len(labels) >= 2 and all(_LABEL.fullmatch(label) for label in labels)


def normalise_valid(raw: str) -> str:
    """Normalised domain, or 422 validation_failed when it is not a host name."""
    domain = normalise(raw)
    if not is_valid(domain):
        raise invalid("domain is not a valid host name")
    return domain
