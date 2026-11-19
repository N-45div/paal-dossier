"""Evidence checks use the provider's own log and the published sample corpus."""
import json
import re
import time

import pytest

from conftest import CORPUS
from support import supports, single_sentence

FIELDS = {"legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total"}
SAMPLE = json.loads((CORPUS / "key.json").read_text())


@pytest.mark.parametrize("text,field,value,valid", [
    ("Dana Ruiz has led Acme Robotics as chief executive since 2021.", "ceo", "Dana Ruiz", True),
    ("Acme Robotics CEO: Sam Ortiz.", "ceo", "Sam Ortiz", True),
    ("Acme Robotics was founded in 2014.", "founded_year", 2014, True),
    ("Acme Robotics employs about 120 people.", "headcount_range", "51-200", True),
    ("Acme Robotics is reportedly in talks to raise $40M.", "funding_total", 40000000, False),
    ("Acme Robotics opened a sales office in Porto.", "hq_city", "Porto", False),
    ("Acme Robotics raised $12M.", "funding_total", 12000000, True),
    ("Acme Robotics raised 12 million dollars.", "funding_total", 12000000, True),
    ("Acme Robotics employs 51-200 people.", "headcount_range", "51-200", True),
    ("Acme Robotics employs 50-51 people.", "headcount_range", "51-200", False),
    ("Acme Robotics is based in Zürich.", "hq_city", "Zürich", True),
    ("Acme Robotics was founded in 2014 and established in 2019.", "founded_year", 2014, False),
    ("Acme Robotics raised $12M. Another sentence.", "funding_total", 12000000, False),
])
def test_oracle_examples(text, field, value, valid):
    """R1.44 R1.45 R1.55 R1.144 R1.145 R1.146 R1.147 R1.148 R1.149 R1.150 R1.151 R1.152 R1.154 R1.155 R1.156 R1.157 R1.158 R1.160 R1.161 R1.162."""
    assert supports(text, "acme-robotics.test", field, value) is valid


@pytest.mark.parametrize("domain", sorted(d for d, entry in SAMPLE.items() if "expected" in entry))
def test_sample_dossier_evidence(client, domain):
    """R1.1 R1.5 R1.44 R1.49 R1.50 R1.52 R1.53 R1.54 R1.55 R1.56 R1.57 R1.58 R1.59 R1.104 R1.153 R1.159 RL1.13."""
    c = client
    token = c.login()
    response = c.request("POST", "/dossiers", headers=c.auth(token, "sample"), json={"domain": domain})
    assert response.status_code == 202
    dossier = c.finish(domain, token)
    assert dossier["state"] == "ready"
    log = c.calls()
    expected = SAMPLE[domain]["expected"]["1"]["0"]
    pages = {}
    for path in CORPUS.glob("*.test.json"):
        company = json.loads(path.read_text())
        for page in company["pages"]:
            if 0 in page["epochs"]:
                pages.setdefault(page["url"], []).append(page["text"])
    for field in FIELDS:
        actual = dossier["fields"][field]
        expected_values = expected.get(field)
        if not isinstance(expected_values, list):
            expected_values = [expected_values]
        assert actual["value"] in expected_values, (domain, field, actual, expected_values)
        if actual["value"] is None:
            assert actual["citations"] == [] and actual["status"] == "unknown"
            continue
        assert actual["status"] == "known" and 1 <= len(actual["citations"]) <= 3
        for citation in actual["citations"]:
            url, excerpt, provider = citation["url"], citation["excerpt"], citation["provider"]
            assert provider in ("nimble", "tavily") and 1 <= len(excerpt) <= 500
            assert single_sentence(excerpt) and supports(excerpt, domain, field, actual["value"]), (field, citation)
            normalized = " ".join(excerpt.split())
            assert url in pages and any(normalized in " ".join(text.split()) for text in pages[url])
            assert any(provider == call["provider"] and any(s["url"] == url and normalized in " ".join(s["text"].split()) for s in call["served"]) for call in log), citation


def test_unsupported_ambiguous_research_and_header(client):
    """R1.45 R1.54 R1.56 R1.58 R1.59 R1.104 R1.146 R1.153 R1.157 R1.159 RL1.13."""
    c = client
    token = c.login()
    domain = "ledger-test.test"
    assert c.request("POST", "/dossiers", headers=c.auth(token, "adversarial"), json={"domain": domain}).status_code == 202
    dossier = c.finish(domain, token)
    assert dossier["state"] == "ready"
    expected = {"legal_name": "Ledger Test, Inc.", "hq_city": "Zürich", "ceo": "Dana Ruiz",
                "founded_year": None, "headcount_range": None, "funding_total": 12500000}
    for field, value in expected.items():
        result = dossier["fields"][field]
        assert result["value"] == value, (field, result)
        for citation in result["citations"]:
            assert supports(citation["excerpt"], domain, field, value)


def test_same_url_with_distinct_search_and_research_text(client):
    """R1.1 R1.50 R1.53 R1.56 R1.104: retain every text served for the same URL."""
    c = client
    token = c.login()
    domain = "split-proof.test"
    url = "https://split-proof.test/about"
    response = c.request("POST", "/dossiers", headers=c.auth(token, "split-evidence"), json={"domain": domain})
    assert response.status_code == 202
    dossier = c.finish(domain, token)
    assert dossier["state"] == "ready"
    calls = c.calls()
    search = [item["text"] for call in calls if call["method"] == "search" for item in call["served"] if item["url"] == url]
    research = [item["text"] for call in calls if call["method"] == "research" for item in call["served"] if item["url"] == url]
    assert any("Split Proof was founded in 2014." in text for text in search), search
    assert any("Split Proof CEO: Dana Ruiz." in text for text in research), research
    assert sum(call["cost"] for call in calls) <= 80
    for field, value in (("founded_year", 2014), ("ceo", "Dana Ruiz")):
        result = dossier["fields"][field]
        assert result["status"] == "known" and result["value"] == value and result["citations"], (field, result)
        for citation in result["citations"]:
            excerpt = " ".join(citation["excerpt"].split())
            assert supports(excerpt, domain, field, value)
            assert any(call["provider"] == citation["provider"] and any(item["url"] == citation["url"] and excerpt in " ".join(item["text"].split()) for item in call["served"]) for call in calls)


def test_same_url_changes_between_search_and_extract(client):
    """R1.1 R1.50 R1.53 R1.104: earlier search evidence survives a later different extract."""
    c = client
    domain = "epoch-proof.test"
    url = "https://epoch-proof.test/about"
    token = c.login()
    c.control("faults", {"provider": "nimble", "methods": ["extract"], "mode": "delay", "seconds": 2})
    response = c.request("POST", "/dossiers", headers=c.auth(token, "epoch-evidence"), json={"domain": domain})
    assert response.status_code == 202
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        calls = c.calls()
        if any(call["method"] == "search" and any(item["url"] == url and "Epoch Proof was founded in 2014." in item["text"] for item in call["served"]) for call in calls):
            break
        time.sleep(.02)
    else:
        pytest.fail("No search served the original epoch's page")
    c.control("epoch", {"epoch": 1})
    dossier = c.finish(domain, token, seconds=45)
    assert dossier["state"] == "ready"
    calls = c.calls()
    assert any(call["method"] == "extract" and any(item["url"] == url and "Epoch Proof CEO: Dana Ruiz." in item["text"] for item in call["served"]) for call in calls), "Extract did not serve the changed page"
    assert sum(call["cost"] for call in calls) <= 80
    for field, value in (("founded_year", 2014), ("ceo", "Dana Ruiz")):
        result = dossier["fields"][field]
        assert result["status"] == "known" and result["value"] == value and result["citations"], (field, result)
        for citation in result["citations"]:
            excerpt = " ".join(citation["excerpt"].split())
            assert supports(excerpt, domain, field, value)
            assert any(call["provider"] == citation["provider"] and any(item["url"] == citation["url"] and excerpt in " ".join(item["text"].split()) for item in call["served"]) for call in calls)


def test_supported_fragment_of_long_sentence(client):
    """R1.53 R1.104: supported fragments of long served sentences are usable; negated sentences are not."""
    c = client
    token = c.login()
    domain = "long-proof.test"
    response = c.request("POST", "/dossiers", headers=c.auth(token, "long-evidence"), json={"domain": domain})
    assert response.status_code == 202
    dossier = c.finish(domain, token)
    assert dossier["state"] == "ready"
    calls = c.calls()
    founded_text = [item["text"] for call in calls for item in call["served"]
                    if item["url"] == "https://long-proof.test/founded" and "Long Proof was founded in 2014." in item["text"]]
    assert founded_text and any(len(text) > 500 for text in founded_text)
    for field, value in (("founded_year", 2014), ("ceo", "Dana Ruiz")):
        result = dossier["fields"][field]
        assert result["status"] == "known" and result["value"] == value and result["citations"], (field, result)
        for citation in result["citations"]:
            excerpt = " ".join(citation["excerpt"].split())
            assert 1 <= len(excerpt) <= 500 and supports(excerpt, domain, field, value)
            assert any(call["provider"] == citation["provider"] and any(item["url"] == citation["url"] and excerpt in " ".join(item["text"].split()) for item in call["served"]) for call in calls)
    assert dossier["fields"]["headcount_range"] == {"value": None, "status": "unknown", "citations": []}


def test_long_sentence_ceo_adjacent_to_company_name(client):
    """R1.53 R1.104 R1.155: company and CEO phrase separate a person's name before parsing."""
    c = client
    token = c.login()
    domain, url = "people-split.test", "https://people-split.test/about"
    response = c.request("POST", "/dossiers", headers=c.auth(token, "long-name"), json={"domain": domain})
    assert response.status_code == 202
    dossier = c.finish(domain, token)
    assert dossier["state"] == "ready"
    calls = c.calls()
    texts = [item["text"] for call in calls for item in call["served"]
             if item["url"] == url and "Dana Ruiz People Split CEO" in item["text"]]
    assert texts and any(len(text) > 500 for text in texts)
    result = dossier["fields"]["ceo"]
    assert result["status"] == "known" and result["value"] == "Dana Ruiz" and result["citations"]
    for citation in result["citations"]:
        excerpt = " ".join(citation["excerpt"].split())
        assert 1 <= len(excerpt) <= 500 and supports(excerpt, domain, "ceo", "Dana Ruiz")
        assert any(call["provider"] == citation["provider"] and any(item["url"] == citation["url"] and excerpt in " ".join(item["text"].split()) for item in call["served"]) for call in calls)
