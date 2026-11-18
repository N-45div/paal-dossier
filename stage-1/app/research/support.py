"""When an excerpt supports a value (Appendix A.2): the whole rule."""
from __future__ import annotations

from typing import Optional, Union

from .formats import EXTRACTORS, NEGATION_PATTERN, Company, phrase_pattern
from .sentences import is_single_sentence
from .words import collapse_whitespace

Value = Union[str, int]


def supported_values(excerpt: str, domain: str) -> dict[str, Value]:
    """Every field the excerpt supports, with its value."""
    text = collapse_whitespace(excerpt)
    if not text or not is_single_sentence(text):
        return {}
    company = Company(domain)
    if not company.names_pattern.search(text) or NEGATION_PATTERN.search(text):
        return {}
    supported: dict[str, Value] = {}
    for field, extract in EXTRACTORS.items():
        if not phrase_pattern(field).search(text):
            continue
        values = extract(text, company)
        if values and all(v == values[0] for v in values):
            supported[field] = values[0]
    return supported


def supports(excerpt: str, domain: str, field: str) -> Optional[Value]:
    """The value of ``field`` the excerpt supports for the company, or None."""
    return supported_values(excerpt, domain).get(field)
