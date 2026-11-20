"""Appendix A: which single excerpts support which field values for a company."""

from .fields import FIELDS
from .lexicon import NEGATING_PHRASES
from .matching import whole_words
from .sentences import collapse_whitespace, split_sentences
from .values import (
    ceo_names,
    company_pattern,
    find_amounts,
    founded_years,
    funding_totals,
    headcount_ranges,
    headquarters_cities,
    legal_names,
    statement_present,
)

_NEGATION = whole_words(NEGATING_PHRASES)


def supports(excerpt: str, domain: str) -> list[tuple[str, object]]:
    """Distinct (field, normalised value) pairs that the single excerpt supports for the company at domain."""
    sentence = collapse_whitespace(excerpt)
    if len(split_sentences(sentence)) != 1:
        return []
    company = company_pattern(domain)
    if company.search(sentence) is None or _NEGATION.search(sentence) is not None:
        return []
    amounts = find_amounts(sentence)
    supported: list[tuple[str, object]] = []
    for field in FIELDS:
        if not statement_present(field, sentence):
            continue
        values = _field_values(field, sentence, company, amounts)
        if len(values) == 1:
            (value,) = values
            if value is not None:
                supported.append((field, value))
    return supported


def _field_values(field, sentence, company, amounts) -> set:
    if field == "legal_name":
        return legal_names(sentence, company)
    if field == "hq_city":
        return headquarters_cities(sentence)
    if field == "ceo":
        return ceo_names(sentence, company)
    if field == "founded_year":
        return founded_years(sentence, amounts)
    if field == "headcount_range":
        return headcount_ranges(sentence, amounts)
    return funding_totals(amounts)
