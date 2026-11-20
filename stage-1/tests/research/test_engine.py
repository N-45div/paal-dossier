"""One build against a fake provider: one domain search, the cap, and what is gathered."""

import time

from research.budget import UNIT_CAP, Budget
from research.calls import Refused
from research.budget import RESEARCH_UNITS
from research.engine import _build, company_name
from research.nimble import Citation

ACME = "acme-robotics.test"
PAGE = "Acme Robotics was founded in 2014.\nAcme Robotics is headquartered in Lisbon."


class FakeProvider:
    def __init__(self, results=None, pages=None, citations=None, research_error=None, search_error=None):
        self.searches = []
        self.extracts = []
        self._results = results if results is not None else ["https://acme-robotics.test/about"]
        self._pages = pages if pages is not None else {"https://acme-robotics.test/about": PAGE}
        self._citations = citations or []
        self._research_error = research_error
        self._search_error = search_error

    def search(self, query):
        self.searches.append(query)
        if self._search_error:
            raise self._search_error
        return list(self._results)

    def extract(self, url):
        self.extracts.append(url)
        return self._pages.get(url)

    def research(self, query):
        if self._research_error:
            raise self._research_error
        return list(self._citations)


def run(provider, budget=None):
    budget = budget or Budget()
    return _build(ACME, provider, budget, time.monotonic() + 60), budget


def test_company_name_from_first_label():
    assert company_name("acme-robotics.test") == "Acme Robotics"


def test_exactly_one_domain_search_and_name_searches_use_other_queries():
    provider = FakeProvider()
    run(provider)
    assert provider.searches.count(ACME) == 1
    others = [q for q in provider.searches if q != ACME]
    assert others and all("Acme Robotics" in q for q in others)


def test_builds_fields_from_gathered_page_and_charges_its_units():
    provider = FakeProvider()
    outcome, budget = run(provider)
    assert outcome.ok
    assert outcome.fields["founded_year"]["value"] == 2014
    assert outcome.fields["hq_city"]["value"] == "Lisbon"
    assert outcome.spent_units == budget.spent
    # every search and extract costs 1, the research run costs 25 (the fake answers no citations)
    assert outcome.spent_units == len(provider.searches) + len(provider.extracts) + RESEARCH_UNITS


def test_research_citation_page_is_fetched_and_its_excerpt_used():
    cited = "https://companies-register.test/entity/1"
    pages = {cited: "Acme Robotics trades under the registered name Acme Robotics Inc. in all markets."}
    citations = [Citation("legal_name", cited, "Acme Robotics trades under the registered name Acme Robotics Inc. in all markets.")]
    outcome, _ = run(FakeProvider(results=[], pages=pages, citations=citations))
    assert outcome.fields["legal_name"]["value"] == "Acme Robotics Inc."
    assert outcome.fields["legal_name"]["citations"][0]["url"] == cited


def test_research_claim_without_supporting_excerpt_is_not_asserted():
    cited = "https://companies-register.test/entity/2"
    pages = {cited: "Acme Robotics is a fine company."}
    citations = [Citation("ceo", cited, "Acme Robotics is a fine company.")]
    outcome, _ = run(FakeProvider(results=[], pages=pages, citations=citations))
    assert outcome.fields["ceo"] == {"value": None, "citations": []}


def test_all_providers_refused_is_failed_and_free():
    provider = FakeProvider(
        search_error=Refused("500"), research_error=Refused("500"), pages={}, results=[]
    )
    outcome, budget = run(provider)
    assert outcome.ok is False
    assert outcome.spent_units == 0
    assert budget.spent == 0


def test_spend_never_exceeds_cap_even_with_many_results():
    many = [f"https://acme-robotics.test/page-{i}" for i in range(200)]
    pages = {url: "Acme Robotics was founded in 2014." for url in many}
    citations = [Citation("funding_total", "https://x.test/y", "x")]
    outcome, budget = run(FakeProvider(results=many, pages=pages, citations=citations))
    assert outcome.spent_units <= UNIT_CAP
    assert budget.spent <= UNIT_CAP


def test_targeted_round_searches_phrases_of_unknown_fields_once():
    provider = FakeProvider(pages={})  # no page supports anything, so every field is unknown
    run(provider)
    assert "Acme Robotics headquartered in" in provider.searches
    assert "Acme Robotics chief executive officer" in provider.searches
    assert len(provider.searches) == len(set(provider.searches))  # no query is ever repeated


def test_targeted_round_is_skipped_when_every_field_is_known():
    page = "Acme Robotics is headquartered in Lisbon. Acme Robotics CEO: Sam Ortiz. Acme Robotics, Inc. is the legal name. Acme Robotics was founded in 2014. Acme Robotics employs 120 people. Acme Robotics has raised $12M."
    provider = FakeProvider(pages={"https://acme-robotics.test/about": page})
    outcome, _ = run(provider)
    assert all(v["value"] is not None for v in outcome.fields.values())
    assert not any("headquartered in" in q for q in provider.searches)
