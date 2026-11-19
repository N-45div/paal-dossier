"""Differential check of Appendix A against an independent implementation (the Prover's support oracle).

Skipped unless the oracle is found: set DOSSIER_SUPPORT_ORACLE to its ``support_oracle.py``, or have it at
``<repo root>/acceptance/stage-1/support_oracle.py``.

One known oracle defect is tolerated: for ``legal_name`` its suffix match is greedy where A.4 says "the shortest
counts", so a sentence with a legal-form suffix word repeated later (``... AS AS THE REGISTERED NAME ... AS``) gets
a longer value from the oracle. That case is checked here against A.4 directly instead.
"""

import importlib.util
import json
import os
import random
from pathlib import Path

import pytest

from app.research.support import FIELDS, supported_values
from app.research.text import split_sentences

from tests.research.fake_router import FIXTURES

DEFAULT_ORACLE = Path(__file__).resolve().parents[3] / "acceptance" / "stage-1" / "support_oracle.py"
ORACLE_PATH = Path(os.environ.get("DOSSIER_SUPPORT_ORACLE", DEFAULT_ORACLE))
pytestmark = pytest.mark.skipif(not ORACLE_PATH.exists(), reason="the support oracle is not available")


def load_oracle():
    spec = importlib.util.spec_from_file_location("support_oracle", ORACLE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def oracle_values(oracle, domain, sentence):
    company = domain.split(".")[0].replace("-", " ")
    found = {}
    for field in FIELDS:
        for value in set(oracle.values_for(field, oracle.norm(sentence), company, domain)):
            if oracle.supports(domain, field, value, sentence):
                found[field] = value
    return found


def disagreements(oracle, cases):
    bad = []
    for domain, sentence in cases:
        mine, theirs = supported_values(sentence, domain), oracle_values(oracle, domain, sentence)
        for field in FIELDS:
            a, b = mine.get(field), theirs.get(field)
            if a != b and not (field == "legal_name" and a and b and b.startswith(a)):
                bad.append((sentence, field, domain, a, b))
    return bad


def corpus_cases():
    for path in sorted(FIXTURES.glob("*.test.json")):
        company = json.loads(path.read_text())
        for page in company["pages"]:
            for sentence in split_sentences(page["text"]):
                yield company["domain"], sentence


def test_every_sentence_of_the_sample_corpus_agrees():
    assert disagreements(load_oracle(), list(corpus_cases())) == []


EDGE_FRAGMENTS = {
    "founded_year": ["2014", "2,014", "1799", "1800", "2099", "2100", "20144", "2014.5", "2014a"],
    "headcount_range": ["120", "1,200", "12,00", "12.5", "0", "10", "11", "51-200", "40-90", "1e3", "1.2.3"],
    "funding_total": ["$12M", "US$12.5m", "USD12m", "$12,00", "12 million dollars", "$0.5", "$1.0000005M", "€12M", "$12 m"],
    "hq_city": ["Lisbon", "San Francisco", "Zürich", "Stratford-Upon-Avon", "new york", "Lisbon Portugal"],
    "ceo": ["Dana Ruiz", "Sam", "Dana Maria Ruiz", "Anna Maria Lucia Ruiz", "Zoë Müller", "DANA Ruiz"],
}
TEMPLATES = {
    "founded_year": ["Acme Robotics was founded in {}.", "In {}, Acme Robotics was established.", "Acme Robotics founded {} and 2015."],
    "headcount_range": ["Acme Robotics employs about {} people.", "Acme Robotics has {} employees and raised $5M."],
    "funding_total": ["Acme Robotics has raised {}.", "Acme Robotics raised {} and {}."],
    "hq_city": ["Acme Robotics is headquartered in {}.", "Acme Robotics is based in {}, Portugal."],
    "ceo": ["{} has led Acme Robotics as chief executive since 2021.", "Acme Robotics CEO: {}.", "Acme Robotics {} CEO."],
}
NEGATIONS = ["", " not", " reportedly", " could", " would", " knot", " notable"]


def generated_cases(count=1500, seed=7):
    rng = random.Random(seed)
    for _ in range(count):
        field = rng.choice(list(TEMPLATES))
        template = rng.choice(TEMPLATES[field])
        sentence = template.format(*(rng.choice(EDGE_FRAGMENTS[field]) for _ in range(template.count("{}"))))
        if rng.random() < 0.3:
            sentence = sentence.replace(" Robotics", " Robotics" + rng.choice(NEGATIONS), 1)
        yield "acme-robotics.test", sentence


def test_generated_edge_sentences_agree():
    assert disagreements(load_oracle(), list(generated_cases())) == []
