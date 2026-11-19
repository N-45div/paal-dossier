"""The evidence strategy (RL1.12-RL1.13, R1.51, R1.131-R1.132) against a scripted gateway."""

import threading

from dossier.engine.build import EXTRA_QUERY_TEMPLATES, build_fields
from dossier.engine.providers import ERROR, OK, TIMEOUT, Answer, Claim, Page
from dossier.engine.result import FIELD_NAMES
from fakes import FakeGateway

D = "acme-robotics.test"
BARE_KEY = ("search", D, "nimble", "fast")


def page(url, text, provider="nimble"):
    return Page(url=url, title="t", text=text, provider=provider)


def search_key(query, provider="nimble", depth="fast"):
    return ("search", query, provider, depth)


def test_one_counted_bare_domain_search_with_fast_nimble():
    gateway = FakeGateway()
    build_fields(D, gateway)
    bare_calls = [c for c in gateway.calls if c[0] == "search" and c[1] == D]
    assert bare_calls == [BARE_KEY]


def test_extra_queries_name_the_company_and_differ_from_domain():
    gateway = FakeGateway()
    build_fields(D, gateway)
    queries = [c[1] for c in gateway.calls if c[0] == "search"]
    assert queries[0] == D
    assert queries[1:] == [t.format(name="Acme Robotics") for t in EXTRA_QUERY_TEMPLATES]


def test_bare_search_retried_only_after_error():
    gateway = FakeGateway(answers={BARE_KEY: [Answer(ERROR), Answer(OK, (page("https://acme-robotics.test/", "x."),))]})
    build_fields(D, gateway)
    bare_calls = [c for c in gateway.calls if c[0] == "search" and c[1] == D]
    assert len(bare_calls) == 2


def test_bare_search_not_retried_after_timeout():
    gateway = FakeGateway(answers={BARE_KEY: Answer(TIMEOUT)})
    build_fields(D, gateway)
    bare_calls = [c for c in gateway.calls if c[0] == "search" and c[1] == D]
    assert len(bare_calls) == 1


def test_timeout_is_charged_in_full():
    gateway = FakeGateway(answers={BARE_KEY: Answer(TIMEOUT)})
    result = build_fields(D, gateway)
    assert gateway.spent >= 5
    assert result.spent_units == gateway.spent


def test_tavily_only_after_nimble_error_and_for_other_queries():
    gateway = FakeGateway(answers={search_key(t.format(name="Acme Robotics")): Answer(ERROR) for t in EXTRA_QUERY_TEMPLATES})
    build_fields(D, gateway)
    tavily = [c for c in gateway.calls if c[0] == "search" and c[2] == "tavily"]
    assert [c[1] for c in tavily] == [t.format(name="Acme Robotics") for t in EXTRA_QUERY_TEMPLATES]
    assert all(c[1] != D for c in tavily)


def test_no_tavily_when_nimble_answers_ok():
    gateway = FakeGateway()
    build_fields(D, gateway)
    assert not [c for c in gateway.calls if c[2] == "tavily"]


def test_spend_never_exceeds_budget_when_every_call_times_out():
    class AllTimeouts(FakeGateway):
        def _call(self, key, units):
            self.calls.append(key)
            self._spent += units
            return Answer(TIMEOUT)

    gateway = AllTimeouts(budget=80)
    result = build_fields(D, gateway)
    assert result.spent_units <= 80
    assert gateway.spent <= 80


def test_extract_candidates_company_site_first_capped_at_eight():
    pages = [page(f"https://news{i}.example/{i}", "x.") for i in range(10)]
    pages.insert(3, page("https://www.acme-robotics.test/about", "x."))
    gateway = FakeGateway(answers={search_key(D): Answer(OK, tuple(pages))})
    build_fields(D, gateway)
    extract = [c for c in gateway.calls if c[0] == "extract"]
    assert len(extract) == 1
    urls = extract[0][1]
    assert len(urls) <= 8
    assert urls[0] == "https://www.acme-robotics.test/about"


def test_extract_not_called_without_candidate_urls():
    gateway = FakeGateway()
    build_fields(D, gateway)
    assert not [c for c in gateway.calls if c[0] == "extract"]


def test_research_asks_for_all_six_fields_by_domain():
    gateway = FakeGateway()
    build_fields(D, gateway)
    research = [c for c in gateway.calls if c[0] == "research"]
    assert research == [("research", D, tuple(FIELD_NAMES))]


def test_research_claim_asserted_only_when_citation_supports_it():
    claims = (
        Claim("founded_year", 2014, "https://acme-robotics.test/about", "Acme Robotics was founded in 2014.", "nimble"),
        Claim("founded_year", 2015, "https://acme-robotics.test/about", "Acme Robotics was founded in 2014.", "nimble"),
        Claim("ceo", "Dana Ruiz", "https://acme-robotics.test/about", "Acme Robotics was founded in 2014.", "nimble"),
    )
    gateway = FakeGateway(answers={("research", D, tuple(FIELD_NAMES)): Answer(OK, claims)})
    result = build_fields(D, gateway)
    assert result.fields["founded_year"].value == 2014
    assert result.fields["founded_year"].citations == [
        {"url": "https://acme-robotics.test/about", "excerpt": "Acme Robotics was founded in 2014.", "provider": "nimble"}
    ]
    assert result.fields["ceo"].value is None
    assert result.fields["ceo"].citations == []


def test_research_claim_with_formatted_number_is_canonicalised():
    claims = (
        Claim("funding_total", "12,000,000", "https://x.test/", "Acme Robotics has raised $12M.", "nimble"),
    )
    gateway = FakeGateway(answers={("research", D, tuple(FIELD_NAMES)): Answer(OK, claims)})
    result = build_fields(D, gateway)
    assert result.fields["funding_total"].value == 12000000


def test_field_value_chosen_by_most_distinct_pages():
    pages = (
        page("https://a.test/1", "Acme Robotics has 120 employees."),
        page("https://a.test/2", "Acme Robotics employs 120 people."),
        page("https://b.test/1", "Acme Robotics employs 20 people."),
        page("https://b.test/1", "Acme Robotics employs 30 people."),
    )
    gateway = FakeGateway(answers={BARE_KEY: Answer(OK, pages)})
    result = build_fields(D, gateway)
    field = result.fields["headcount_range"]
    assert field.value == "51-200"
    assert {c["url"] for c in field.citations} == {"https://a.test/1", "https://a.test/2"}


def test_ties_broken_by_ascending_string_form_and_numeric_for_numbers():
    pages = (
        page("https://a.test/1", "Acme Robotics was founded in 2019."),
        page("https://b.test/1", "Acme Robotics was founded in 2014."),
    )
    gateway = FakeGateway(answers={BARE_KEY: Answer(OK, pages)})
    result = build_fields(D, gateway)
    assert result.fields["founded_year"].value == 2014
    assert all(c["excerpt"] != "Acme Robotics was founded in 2019." for c in result.fields["founded_year"].citations)


def test_string_tie_broken_by_string_form():
    pages = (
        page("https://a.test/1", "Acme Robotics is based in Zurich."),
        page("https://b.test/1", "Acme Robotics is based in Berlin."),
    )
    gateway = FakeGateway(answers={BARE_KEY: Answer(OK, pages)})
    assert build_fields(D, gateway).fields["hq_city"].value == "Berlin"


def test_at_most_three_citations_distinct_pages_first():
    pages = (
        page("https://a.test/1", "Acme Robotics was founded in 2014."),
        page("https://a.test/2", "Acme Robotics was founded in 2014."),
        page("https://a.test/3", "Acme Robotics was founded in 2014."),
        page("https://a.test/4", "Acme Robotics was founded in 2014."),
        page("https://a.test/4", "Acme Robotics was established in 2014."),
    )
    gateway = FakeGateway(answers={BARE_KEY: Answer(OK, pages)})
    cites = build_fields(D, gateway).fields["founded_year"].citations
    assert len(cites) == 3
    assert len({c["url"] for c in cites}) == 3


def test_header_and_facts_are_never_cited_or_used():
    text = 'Title: Acme\nFacts: {"founded_year": 2014}\n\nAcme Robotics has a staff of 900.'
    gateway = FakeGateway(answers={BARE_KEY: Answer(OK, (page("https://a.test/1", text),))})
    result = build_fields(D, gateway)
    assert result.fields["founded_year"].value is None
    assert result.fields["headcount_range"].value == "501-1000"
    assert all("Facts" not in c["excerpt"] for c in result.fields["headcount_range"].citations)


def test_provider_of_citation_is_the_serving_provider():
    gateway = FakeGateway(answers={BARE_KEY: Answer(OK, (page("https://a.test/1", "Acme Robotics was founded in 2014.", "nimble"),))})
    cite = build_fields(D, gateway).fields["founded_year"].citations[0]
    assert cite["provider"] == "nimble" and cite["url"] == "https://a.test/1"


def test_no_success_means_not_ok_and_unknown_fields():
    class AllErrors(FakeGateway):
        def _call(self, key, units):
            self.calls.append(key)
            return Answer(ERROR)

    gateway = AllErrors()
    result = build_fields(D, gateway)
    assert result.ok is False
    assert result.spent_units == 0
    assert all(result.fields[name].value is None for name in FIELD_NAMES)


def test_ok_when_any_call_succeeds_even_with_no_facts():
    gateway = FakeGateway(answers={BARE_KEY: Answer(OK, ())})
    result = build_fields(D, gateway)
    assert result.ok is True
    assert set(result.fields) == set(FIELD_NAMES)


def test_skipped_calls_are_not_made_when_budget_is_gone():
    gateway = FakeGateway(budget=0)
    result = build_fields(D, gateway)
    assert result.spent_units == 0
    assert gateway.calls == []


def test_exhausted_budget_stops_further_calls_and_keeps_evidence():
    class CancelAfterFirst(FakeGateway):
        def search(self, query, provider, depth):
            answer = super().search(query, provider, depth)
            self.budget = self.spent
            return answer

    gateway = CancelAfterFirst(answers={BARE_KEY: Answer(OK, (page("https://a.test/1", "Acme Robotics was founded in 2014."),))})
    result = build_fields(D, gateway)
    assert result.fields["founded_year"].value == 2014
    assert len([c for c in gateway.calls if c[0] == "search"]) == 1


def test_run_build_never_raises_and_reports_not_ok_without_gateway():
    import dossier.engine as engine

    result = engine.run_build(D, threading.Event())
    assert result.ok is False
    assert result.spent_units == 0
    assert set(result.fields) == set(FIELD_NAMES)




def test_different_text_served_for_same_url_is_all_evidence():
    # R1.50: each served text is evidence; a second search serving other text for the
    # same URL must not be discarded, and the extract must not replace it.
    url = "https://acme-robotics.test/about"
    gateway = FakeGateway(
        answers={
            BARE_KEY: Answer(OK, (page(url, "Acme Robotics was founded in 2014."),)),
            search_key(EXTRA_QUERY_TEMPLATES[0].format(name="Acme Robotics")): Answer(
                OK, (page(url, "Acme Robotics CEO: Dana Ruiz."),)
            ),
            ("extract", (url,)): Answer(OK, (page(url, "Acme Robotics was founded in 2014."),)),
        }
    )
    result = build_fields(D, gateway)
    assert result.fields["founded_year"].value == 2014
    assert result.fields["ceo"].value == "Dana Ruiz"
    assert result.fields["ceo"].citations == [
        {"url": url, "excerpt": "Acme Robotics CEO: Dana Ruiz.", "provider": "nimble"}
    ]


def test_two_searches_serving_different_text_for_one_url_both_count():
    url = "https://acme-robotics.test/about"
    gateway = FakeGateway(
        answers={
            BARE_KEY: Answer(OK, (page(url, "Acme Robotics was founded in 2014."),)),
            search_key(EXTRA_QUERY_TEMPLATES[0].format(name="Acme Robotics")): Answer(
                OK, (page(url, "Acme Robotics CEO: Dana Ruiz."),)
            ),
        }
    )
    result = build_fields(D, gateway)
    assert result.fields["founded_year"].value == 2014
    assert result.fields["ceo"].value == "Dana Ruiz"
    assert result.fields["ceo"].citations[0]["url"] == url


def test_search_and_extract_serving_different_text_for_one_url_both_count():
    url = "https://acme-robotics.test/about"
    gateway = FakeGateway(
        answers={
            # the truncated search body carries the CEO sentence
            BARE_KEY: Answer(OK, (page(url, "Acme Robotics CEO: Dana Ruiz."),)),
            # the full extract carries the founding sentence the search body lacks
            ("extract", (url,)): Answer(OK, (page(url, "Acme Robotics was founded in 2014."),)),
        }
    )
    result = build_fields(D, gateway)
    assert result.fields["ceo"].value == "Dana Ruiz"
    assert result.fields["founded_year"].value == 2014
    assert result.fields["founded_year"].citations == [
        {"url": url, "excerpt": "Acme Robotics was founded in 2014.", "provider": "nimble"}
    ]


def test_research_snippet_is_evidence_only_through_its_own_text():
    url = "https://acme-robotics.test/about"
    claims = (
        Claim("ceo", "Dana Ruiz", url, "Acme Robotics CEO: Dana Ruiz.", "nimble"),
        # a claim whose own snippet does not support its value adds nothing
        Claim("founded_year", 2014, url, "Acme Robotics CEO: Dana Ruiz.", "nimble"),
    )
    gateway = FakeGateway(
        answers={
            BARE_KEY: Answer(OK, (page(url, "Acme Robotics was founded in 2015."),)),
            ("research", D, tuple(FIELD_NAMES)): Answer(OK, claims),
        }
    )
    result = build_fields(D, gateway)
    assert result.fields["ceo"].value == "Dana Ruiz"
    assert result.fields["ceo"].citations == [
        {"url": url, "excerpt": "Acme Robotics CEO: Dana Ruiz.", "provider": "nimble"}
    ]
    assert result.fields["founded_year"].value == 2015
    assert all(c["excerpt"] != "Acme Robotics CEO: Dana Ruiz." for c in result.fields["founded_year"].citations)


def test_long_served_sentence_still_makes_the_field_known():
    # R1.104: a supported value inside a 545-character served sentence is known, and the
    # citation is the fragment that supports it on its own.
    url = "https://acme-robotics.test/about"
    long_sentence = "Acme Robotics was founded in 2014 and " + ("zeta " * 103).strip()
    gateway = FakeGateway(answers={BARE_KEY: Answer(OK, (page(url, long_sentence),))})
    result = build_fields(D, gateway)
    assert result.fields["founded_year"].value == 2014
    assert result.fields["founded_year"].citations == [
        {"url": url, "excerpt": "Acme Robotics was founded in 2014", "provider": "nimble"}
    ]
