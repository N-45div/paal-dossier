"""The service's support decision matches the labels shipped with the sample corpus."""
import json
from pathlib import Path

import pytest

from app.research.formats import EXTRACTORS
from app.research.pages import prose_of
from app.research.sentences import split_prose
from app.research.support import supported_values

FIXTURES = Path(__file__).parent / "fixtures" / "sample"
KEY = json.loads((FIXTURES / "key.json").read_text())
LABELLED = [d for d, v in KEY.items() if v.get("supports")]


def labels(domain):
    """Labels for the six stage-1 fields (the key also labels later-stage fields)."""
    return [s for s in KEY[domain]["supports"] if s["field"] in EXTRACTORS]


def served_text(page):
    header = [f"Registrant: {page['lineage']['registrant']}"]
    return "\n".join(header) + "\n\n" + page["text"]


@pytest.mark.parametrize("domain", LABELLED)
def test_R1_46_R1_129_labels_are_supported(domain):
    for label in labels(domain):
        got = supported_values(label["excerpt"], domain)
        assert got.get(label["field"]) == label["value"], label


@pytest.mark.parametrize("domain", LABELLED)
def test_R1_46_R1_82_every_sentence_matches_labels(domain):
    company = json.loads((FIXTURES / f"{domain}.json").read_text())
    expected = {(s["excerpt"], s["field"], s["value"]) for s in labels(domain)}
    found = set()
    for page in company["pages"]:
        for sentence in split_prose(prose_of(served_text(page))):
            for field, value in supported_values(sentence, domain).items():
                found.add((sentence, field, value))
    assert found == expected
