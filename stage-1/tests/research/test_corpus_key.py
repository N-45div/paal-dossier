"""Every excerpt the sample corpus key labels supports exactly its field and value, and nothing else."""

import json
from pathlib import Path

import pytest

from app.research.support import FIELDS, supported_values

FIXTURES = Path(__file__).parent / "fixtures"
KEY = json.loads((FIXTURES / "key.json").read_text())
LABELLED = [
    (domain, s)
    for domain, entry in KEY.items()
    for s in entry.get("supports", [])
    if s["field"] in FIELDS
]


@pytest.mark.parametrize("domain,label", LABELLED, ids=[f"{d}:{s['field']}" for d, s in LABELLED])
def test_labelled_excerpt_supports_exactly_its_value(domain, label):
    assert supported_values(label["excerpt"], domain) == {label["field"]: label["value"]}


def test_every_labelled_excerpt_is_in_its_page():
    for domain, label in LABELLED:
        company = json.loads((FIXTURES / f"{domain}.json").read_text())
        pages = [p for p in company["pages"] if p["url"] == label["url"]]
        assert any(label["excerpt"] in p["text"] for p in pages)
