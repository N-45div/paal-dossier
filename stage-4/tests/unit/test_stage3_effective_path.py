"""Stage 3 true_from along the candidate path (R3B, ledger R3.6).

The header block of a served text ends at its first empty line (stage-1 §4 Pages). An
`Effective:` line counts only inside that block. These tests run the served text through
split_header and the candidate builders, so the page version, the candidates and the
executives members must all carry the same true_from.
"""

from datetime import date

from app.evidence import collect_candidates, collect_executives
from app.gateway import ServedPage
from app.pages import page_meta
from app.support import split_header

DOMAIN = "acme-robotics.test"
URL = "https://acme-robotics.test/team"
CEO_SENTENCE = "Ana Silva is the chief executive of Acme Robotics."
CFO_SENTENCE = "Ben Okafor is the chief financial officer of Acme Robotics."


def _served(text: str) -> ServedPage:
    headers, prose = split_header(text)
    return ServedPage(url=URL, prose=prose, headers=headers)


def _ceo_true_from(text: str) -> date | None:
    candidates = collect_candidates(DOMAIN, [_served(text)])["ceo"]
    assert len(candidates) == 1
    return candidates[0].true_from


def test_effective_on_first_header_line_is_true_from():
    text = f"Effective: 2026-02-01\nKind: own\nPublished: 2026-03-20T00:00:00Z\n\n{CEO_SENTENCE}"
    assert _ceo_true_from(text) == date(2026, 2, 1)


def test_effective_on_a_later_header_line_is_true_from():
    text = f"Kind: own\nPublished: 2026-03-20T00:00:00Z\nEffective: 2026-02-01\n\n{CEO_SENTENCE}"
    assert _ceo_true_from(text) == date(2026, 2, 1)


def test_effective_in_prose_is_not_a_header_and_falls_back_to_published():
    # The header ends at the empty line, so this Effective line is prose, not a header line.
    text = f"Kind: own\nPublished: 2026-03-20T00:00:00Z\n\nEffective: 2026-02-01\n\n{CEO_SENTENCE}"
    assert _ceo_true_from(text) == date(2026, 3, 20)


def test_invalid_effective_falls_back_to_utc_date_of_published():
    text = f"Effective: 2026-02-30\nPublished: 2026-03-20T23:30:00-05:00\n\n{CEO_SENTENCE}"
    assert _ceo_true_from(text) == date(2026, 3, 21)


def test_neither_effective_nor_published_gives_null():
    assert _ceo_true_from(f"Kind: own\n\n{CEO_SENTENCE}") is None


def test_page_version_and_executives_member_agree_with_the_candidate():
    text = (f"Effective: 2026-02-01\nPublished: 2026-03-20T00:00:00Z\n\n"
            f"{CEO_SENTENCE} {CFO_SENTENCE}")
    page = _served(text)
    expected = page_meta(page.headers, page.url, DOMAIN).true_from
    assert expected == date(2026, 2, 1)
    assert collect_candidates(DOMAIN, [page])["ceo"][0].true_from == expected
    executives = collect_executives(DOMAIN, [page])
    assert executives and all(member.true_from == expected for member in executives)
