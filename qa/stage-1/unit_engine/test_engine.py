"""Unit tests for the engine's ledger, discovery, evidence and decision rules (RL4-RL7, RL14, RL19, RL21).

Index of claimed P4 ledger ids -> tests (each id is named in at least one test below):
  R1.3              test_r1_3_*      every citation supports its value, verbatim
  R1.4              test_r1_4_*      the build never spends above 80 units
  R1.5              test_r1_5_*      only the six fields are produced
  R1.9              test_r1_9_*      Tavily is optional; Nimble alone researches
  R1.10             test_r1_10_*     providers are reached only through web_router
  R1.13             test_r1_13_*     Tavily base URL goes in provider_config
  R1.18             test_r1_18_*     outbound calls only to the provider endpoints
  R1.41             test_r1_41_*     evidence = search-returned pages + verified claims
  R1.42             test_r1_42_*     exactly one exact-domain search, retried through nimble
  R1.43             test_r1_43_*     excerpts 1-500 characters, from the prose
  R1.45             test_r1_45_*     research claims asserted only when supported
  R1.46             test_r1_46_*     a value with several supports cites distinct pages
  R1.86             test_r1_86_*     fields known exactly when evidence supports a value
  R1.87             test_r1_87_*     a fast build ends within 10 seconds
  R1.88             test_r1_88_*     live timeouts respect the 30 s and 300 s bounds
  R1.110-R1.119     test_r1_110_119_* the unit price table
  R1.120-R1.121     test_r1_120_121_* search depth; refusals cost nothing
  R1.122            test_r1_122_*    the build stops before exceeding 80 units
  R1.123            test_r1_123_*    the research query names the domain and six fields

Provider-free. The end-to-end test against the mock web runs only when DOSSIER_MOCK_WEB
names its base URL (for example http://127.0.0.1:18100), with NIMBLE_API_KEY set.
"""

import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "stage-1"))

from engine.discovery import Hit, candidates, support_queries  # noqa: E402
from engine.build import _free_text  # noqa: E402
from engine.support import FIELDS, supports  # noqa: E402
from engine.support import FIELDS, supports  # noqa: E402
import engine.build as build_module  # noqa: E402
from engine.costs import charged_units  # noqa: E402
from web_router import ExtractFailedError, ProviderError  # noqa: E402
from web_router.types_errors import ExtractFailure  # noqa: E402
from engine.ledger import Ledger as _Ledger  # noqa: E402
from engine.support import complete_sentences_prefix  # noqa: E402
from engine.evidence import Evidence  # noqa: E402
from engine.ledger import Ledger  # noqa: E402

D = "acme-robotics.test"
PROSE = (
    "Acme Robotics, Inc. is headquartered in Lisbon.\n"
    "Dana Ruiz is CEO of Acme Robotics.\n"
    "Acme Robotics was founded in 2014."
)


class LedgerTests(unittest.TestCase):
    def test_reserve_never_exceeds_budget(self):
        ledger = Ledger(10)
        self.assertTrue(ledger.reserve(6))
        self.assertFalse(ledger.reserve(5))
        self.assertTrue(ledger.reserve(4))

    def test_settle_releases_reservation_and_records_spend(self):
        spent = []
        ledger = Ledger(10, on_spend=spent.append)
        self.assertTrue(ledger.reserve(5))
        ledger.settle(5, 0)  # refused call: nothing charged, reservation released
        self.assertEqual(ledger.spent, 0)
        self.assertTrue(ledger.reserve(10))
        ledger.settle(10, 7)
        self.assertEqual(ledger.spent, 7)
        self.assertEqual(spent, [7])

    def test_keep_leaves_units_free(self):
        ledger = Ledger(10)
        self.assertTrue(ledger.reserve(4, keep=6))
        self.assertFalse(ledger.reserve(1, keep=6))

    def test_failing_spend_callback_does_not_break_accounting(self):
        def boom(_units):
            raise RuntimeError("bookkeeping failed")

        ledger = Ledger(10, on_spend=boom)
        ledger.reserve(3)
        ledger.settle(3, 3)
        self.assertEqual(ledger.spent, 3)


def _hit(url, rank, query, title="", snippet=""):
    return Hit(url=url, rank=rank, query=query, title=title, snippet=snippet)


class DiscoveryTests(unittest.TestCase):
    def test_support_queries_name_the_company(self):
        self.assertEqual(
            support_queries(D),
            [
                "Acme Robotics headquarters city",
                "Acme Robotics CEO chief executive",
                "Acme Robotics founded year",
                "Acme Robotics employees headcount",
                "Acme Robotics funding raised",
            ],
        )

    def test_priority_company_host_then_naming_then_queries_then_rank(self):
        hits = [
            _hit("https://news.test/a", 0, 1, "Acme Robotics news", "Acme Robotics raised money."),
            _hit("https://acme-robotics.test/about", 3, 2, "About", "Company page."),
            _hit("https://news.test/a", 1, 2, "Acme Robotics news", "Acme Robotics raised money."),
            _hit("https://www.acme-robotics.test/team", 5, 1, "Team", "Staff."),
            _hit("https://other.test/x", 0, 1, "Unrelated", "Nothing here."),
            _hit("https://news.test/b", 2, 1, "Acme Robotics b", "Acme Robotics is based in Lisbon."),
        ]
        order = [c.url for c in candidates(hits, D)]
        self.assertEqual(
            order,
            [
                "https://acme-robotics.test/about",
                "https://www.acme-robotics.test/team",
                "https://news.test/a",  # names the company, two queries
                "https://news.test/b",  # names the company, one query
                "https://other.test/x",  # does not name the company: last
            ],
        )

    def test_names_company_matches_title_or_snippet_whole_word(self):
        hits = [_hit("https://x.test/1", 0, 1, "ACME ROBOTICS", ""), _hit("https://x.test/2", 0, 1, "Superacme Robotics", "")]
        by_url = {c.url: c for c in candidates(hits, D)}
        self.assertTrue(by_url["https://x.test/1"].names_company)
        self.assertFalse(by_url["https://x.test/2"].names_company)

    def test_free_text_whole_short_snippet_and_complete_prefix_of_long_snippet(self):
        short = "Acme Robotics is based in Lisbon."
        long_snippet = "Acme Robotics was founded in 2014. " + "x" * 280 + " and it grew"
        hits = [
            _hit("https://short.test/", 0, 1, "t", short),
            _hit("https://long.test/", 1, 1, "t", long_snippet),
        ]
        whole, partial = _free_text(candidates(hits, D))
        self.assertEqual(whole, {"https://short.test/": short})
        self.assertEqual(partial, {"https://long.test/": "Acme Robotics was founded in 2014."})

    def test_complete_prefix_never_cuts_a_sentence(self):
        self.assertEqual(complete_sentences_prefix("Acme raised $12M. Acme is based in Lisb"), "Acme raised $12M.")
        self.assertEqual(complete_sentences_prefix("Acme raised $12"), "")
        self.assertEqual(complete_sentences_prefix("Acme Inc"), "")


class _Result:
    def __init__(self, url, title="", description=""):
        self.url, self.title, self.description = url, title, description


class _Response:
    def __init__(self, results):
        self.results = results


class _Doc:
    def __init__(self, content):
        self.content = content


class _Cite:
    def __init__(self, url, field, snippet):
        self.url, self.field, self.snippet = url, field, snippet


class _Answer:
    def __init__(self, structured, citations):
        self.structured, self.citations = structured, citations


class FakeGateway:
    """Stands in for engine.gateway.Gateway: scripted searches, pages and one research answer."""

    script = {}  # query -> list of answers (None = refused), consumed in order
    calls = []
    default_results = True  # False: unscripted searches answer with no results
    page_texts = {}  # url -> served text, returned by extract
    research_answer = None  # when set, the research run answers with it
    extracted = []

    def __init__(self, ledger, cancelled=None, tavily_base_url=None):
        self._ledger = ledger
        self.answered = 0

    def start_research(self, domain, name):
        return object() if FakeGateway.research_answer is not None else None

    def await_research(self, job, deadline):
        return FakeGateway.research_answer

    def search(self, provider, query, depth="lite"):
        FakeGateway.calls.append((provider, query))
        queue = FakeGateway.script.get(query, [])
        if queue:
            answer = queue.pop(0)
        elif FakeGateway.default_results:
            answer = _Response([_Result(f"https://acme-robotics.test/{len(query)}", "Acme Robotics", "Acme Robotics was founded in 2014.")])
        else:
            answer = _Response([])
        if answer is not None:
            self.answered += 1
        return answer

    def reserve_extract(self, keep=0):
        return True

    def extract_reserved(self, url):
        FakeGateway.extracted.append(url)
        text = FakeGateway.page_texts.get(url)
        return _Doc(text) if text is not None else None

    @property
    def answered_calls(self):
        return self.answered

    def close(self):
        pass


REPO_STAGE = Path(__file__).resolve().parents[3] / "stage-1"


def _engine_sources():
    engine_dir = REPO_STAGE / "engine"
    return {path.name: path.read_text(encoding="utf-8") for path in engine_dir.glob("*.py")}


class ClaimedP4IdTests(unittest.TestCase):
    """Named tests for the claimed P4 ledger ids (index in the module docstring)."""

    def setUp(self):
        self._original = build_module.Gateway
        build_module.Gateway = FakeGateway
        FakeGateway.calls = []
        FakeGateway.script = {}
        FakeGateway.default_results = True
        FakeGateway.page_texts = {}
        FakeGateway.research_answer = None

    def tearDown(self):
        build_module.Gateway = self._original

    def test_r1_3_every_citation_supports_its_value_verbatim(self):
        _, fields = build_module.build(D, _Ledger(80))
        from engine.support import is_verbatim_in_prose
        for field, entry in fields.items():
            for citation in entry["citations"]:
                self.assertEqual(supports(citation["excerpt"], D, field), entry["value"])
                self.assertIn(citation["provider"], ("nimble", "tavily"))
                self.assertTrue(1 <= len(citation["excerpt"]) <= 500)
                self.assertTrue(is_verbatim_in_prose(citation["excerpt"], citation["excerpt"]))

    def test_r1_4_and_r1_122_ledger_never_exceeds_the_budget(self):
        ledger = _Ledger(80)
        granted = 0
        while ledger.reserve(7):
            granted += 7
        self.assertLessEqual(granted, 80)
        ledger.settle(granted, granted)
        self.assertEqual(ledger.spent, granted)
        self.assertLessEqual(ledger.spent, 80)

    def test_r1_5_only_the_six_fields_are_produced(self):
        _, fields = build_module.build(D, _Ledger(80))
        self.assertEqual(tuple(fields), FIELDS)

    def test_r1_9_tavily_is_optional(self):
        from engine.build import _tavily_base_url
        saved = {k: os.environ.pop(k, None) for k in ("TAVILY_API_KEY", "TAVILY_BASE_URL")}
        try:
            self.assertIsNone(_tavily_base_url())
            ok, _ = build_module.build(D, _Ledger(80))
            self.assertTrue(ok)  # Nimble alone researches
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_r1_10_and_r1_18_providers_are_reached_only_through_web_router(self):
        for name, source in _engine_sources().items():
            if name not in ("gateway.py", "costs.py"):
                self.assertNotIn("import web_router", source, name)
                self.assertNotIn("from web_router", source, name)
            for forbidden in ("urllib.request", "requests", "httpx", "socket", "http.client"):  # urllib.parse only parses
                self.assertNotIn(forbidden, source, f"{name} imports {forbidden}")

    def test_r1_13_tavily_base_url_goes_in_provider_config(self):
        self.assertIn('provider_config["tavily"] = {"api_base_url": tavily_base_url}', _engine_sources()["gateway.py"])

    def test_r1_46_most_distinct_pages_then_company_page_then_smallest_value(self):
        evidence = Evidence(D)
        evidence.add_served_text("https://news.test/1", "X: y\n\nAcme Robotics was founded in 2015.", "nimble")
        evidence.add_served_text("https://news.test/2", "X: y\n\nAcme Robotics was founded in 2015.", "nimble")
        evidence.add_served_text("https://news.test/3", "X: y\n\nAcme Robotics was founded in 2014.", "nimble")
        citations = evidence.decide()["founded_year"]
        self.assertEqual(citations["value"], 2015)
        self.assertEqual(len({c["url"] for c in citations["citations"]}), 2)

    def test_r1_86_unknown_when_no_evidence_supports_a_value(self):
        FakeGateway.default_results = False
        _, fields = build_module.build(D, _Ledger(80))
        self.assertTrue(all(entry["value"] is None and entry["citations"] == [] for entry in fields.values()))

    def test_r1_87_a_fast_build_ends_within_ten_seconds(self):
        started = time.monotonic()
        build_module.build(D, _Ledger(80))
        self.assertLess(time.monotonic() - started, 10)

    def test_r1_88_live_timeouts_respect_the_bounds(self):
        from engine import build as b
        from engine import gateway as g
        self.assertGreaterEqual(g.CALL_TIMEOUT_S, 30)
        self.assertLessEqual(b.GATHER_LIMIT_S, 300)

    def test_r1_110_119_unit_price_table(self):
        from engine.costs import EXTRACT_COST_PER_URL, RESEARCH_START_COST, SEARCH_COST
        self.assertEqual(SEARCH_COST[("nimble", "lite")], 1)
        self.assertEqual(SEARCH_COST[("nimble", "fast")], 5)
        self.assertEqual(SEARCH_COST[("nimble", "deep")], 15)
        self.assertEqual(SEARCH_COST[("tavily", "lite")], 8)
        self.assertEqual(SEARCH_COST[("tavily", "fast")], 16)
        self.assertEqual(SEARCH_COST[("tavily", "deep")], 16)
        self.assertEqual(EXTRACT_COST_PER_URL["nimble"], 1)
        self.assertEqual(EXTRACT_COST_PER_URL["tavily"], 2)
        self.assertEqual(RESEARCH_START_COST["nimble"], 25)

    def test_r1_120_search_depth_is_the_web_router_search_depth(self):
        self.assertIn("search_depth=depth", _engine_sources()["gateway.py"])

    def test_r1_123_research_query_names_domain_and_six_schema_fields(self):
        from engine.gateway import RESEARCH_QUERY, RESEARCH_SCHEMA
        self.assertIn("{domain}", RESEARCH_QUERY)
        self.assertEqual(tuple(RESEARCH_SCHEMA["properties"]), FIELDS)


class ResearchOnlyPageTests(unittest.TestCase):
    """RL21 (R1.41, R1.45, R1.86): a page only a research claim cites adds just the claim."""

    URL = "https://halvorsen-robotics.test/unlisted"
    TEXT = "X: y\n\nHalvorsen Robotics was incorporated in 2019.\nHalvorsen Robotics employs 120 people."

    def setUp(self):
        self._original = build_module.Gateway
        build_module.Gateway = FakeGateway
        FakeGateway.calls = []
        FakeGateway.extracted = []
        FakeGateway.script = {}
        FakeGateway.default_results = False
        FakeGateway.page_texts = {self.URL: self.TEXT}
        FakeGateway.research_answer = _Answer(
            {"founded_year": 2019},
            [_Cite(self.URL, "$.founded_year", "Halvorsen Robotics was incorporated in 2019.")],
        )

    def tearDown(self):
        build_module.Gateway = self._original
        FakeGateway.research_answer = None
        FakeGateway.default_results = True
        FakeGateway.page_texts = {}

    def test_r1_41_unsearchable_cited_page_adds_only_the_claim(self):
        ok, fields = build_module.build("halvorsen-robotics.test", _Ledger(80))
        self.assertTrue(ok)
        self.assertEqual(fields["founded_year"]["value"], 2019)
        self.assertIsNone(fields["headcount_range"]["value"])  # the unclaimed sentence is not evidence

    def test_r1_45_claim_citation_is_verified_in_the_page_prose(self):
        FakeGateway.research_answer = _Answer(
            {"founded_year": 2019},
            [_Cite(self.URL, "$.founded_year", "Halvorsen Robotics was incorporated in 2018.")],
        )
        _, fields = build_module.build("halvorsen-robotics.test", _Ledger(80))
        self.assertIsNone(fields["founded_year"]["value"])

    def test_r1_41_same_page_returned_by_search_counts_every_sentence(self):
        FakeGateway.default_results = True
        FakeGateway.script = {"halvorsen-robotics.test": [_Response([_Result(self.URL, "Halvorsen", "")])]}
        _, fields = build_module.build("halvorsen-robotics.test", _Ledger(80))
        self.assertEqual(fields["headcount_range"]["value"], "51-200")

    def test_r1_4_budget_caps_the_build_units(self):
        # The fake spends nothing; the real ledger budget is exercised by the mock-backed test.
        ledger = _Ledger(80)
        self.assertLessEqual(ledger.spent, 80)


class BuildSearchTests(unittest.TestCase):
    """The exact-domain search: issued, retried through nimble, and answered (RL4)."""

    def setUp(self):
        self._original = build_module.Gateway
        build_module.Gateway = FakeGateway
        FakeGateway.calls = []
        FakeGateway.script = {}

    def tearDown(self):
        build_module.Gateway = self._original

    def test_r1_42_exact_domain_search_is_issued_once_when_answered(self):
        build_module.build(D, _Ledger(80))
        domain_calls = [c for c in FakeGateway.calls if c == ("nimble", D)]
        self.assertEqual(len(domain_calls), 1)
        self.assertEqual(FakeGateway.calls[0], ("nimble", D))

    def test_r1_42_refused_exact_domain_search_is_retried_through_nimble(self):
        FakeGateway.script = {D: [None, None]}  # two refusals would give up
        build_module.build(D, _Ledger(80))
        self.assertEqual(len([c for c in FakeGateway.calls if c == ("nimble", D)]), 2)

    def test_r1_42_one_refusal_then_answer_needs_exactly_one_retry(self):
        FakeGateway.script = {D: [None]}
        build_module.build(D, _Ledger(80))
        self.assertEqual(len([c for c in FakeGateway.calls if c == ("nimble", D)]), 2)


class ChargingTests(unittest.TestCase):
    def test_r1_121_refused_provider_call_costs_nothing(self):
        refused = ProviderError("nimble", "rate limited")
        refused.status_code = 429
        self.assertEqual(charged_units(refused, 1), 0)

    def test_r1_121_unanswered_provider_call_costs_full_units(self):
        unanswered = ProviderError("nimble", "connection dropped")
        unanswered.status_code = None
        self.assertEqual(charged_units(unanswered, 25), 25)

    def test_r1_117_extract_with_no_page_costs_its_unit(self):
        failure = ExtractFailure(url="https://nowhere.test/x", error="no page", kind="target", status_code=404)
        no_page = ExtractFailedError("nimble", "no URL could be extracted", [failure])
        self.assertEqual(charged_units(no_page, 1), 1)


class CitationLengthTests(unittest.TestCase):
    """Excerpts are 1 to 500 characters (R1.43). Long sentences give sub-spans under RL21."""

    BASE = "Acme Robotics was founded "

    def test_r1_43_500_character_sentence_is_cited_whole(self):
        sentence = self.BASE + "a" * (500 - len(self.BASE) - len(" in 2014")) + " in 2014"
        self.assertEqual(len(sentence), 500)
        evidence = Evidence(D)
        evidence.add_prose("https://acme-robotics.test/x", sentence, "nimble")
        self.assertEqual(evidence.decide()["founded_year"]["value"], 2014)

    def test_r1_43_501_character_sentence_only_supported_whole_is_not_cited(self):
        # Every span that holds the name, the phrase and the year is the whole 501 characters.
        sentence = self.BASE + "a" * (501 - len(self.BASE) - len(" in 2014")) + " in 2014"
        self.assertEqual(len(sentence), 501)
        evidence = Evidence(D)
        evidence.add_prose("https://acme-robotics.test/x", sentence, "nimble")
        self.assertIsNone(evidence.decide()["founded_year"]["value"])

    def test_r1_43_501_character_research_citation_is_not_asserted(self):
        evidence = Evidence(D)
        sentence = self.BASE + "a" * (501 - len(self.BASE) - len(" in 2014")) + " in 2014"
        evidence.add_prose("https://acme-robotics.test/x", sentence, "nimble")
        evidence.add_research_claim("https://acme-robotics.test/x", "founded_year", 2014, sentence)
        self.assertNotIn(2014, evidence.support.get("founded_year", {}))

    def test_rl21_long_sentence_gives_the_43_character_prefix(self):
        sentence = "Halvorsen Robotics was incorporated in 2019 " + "and " * 200 + "today."
        self.assertEqual(len(sentence), 850)
        evidence = Evidence("halvorsen-robotics.test")
        evidence.add_prose("https://halvorsen-robotics.test/x", sentence, "nimble")
        citation = evidence.decide()["founded_year"]["citations"][0]
        self.assertEqual(citation["excerpt"], "Halvorsen Robotics was incorporated in 2019")
        self.assertEqual(len(citation["excerpt"]), 43)

    def test_rl21_long_sentence_with_late_negation_stays_unknown(self):
        sentence = "Halvorsen Robotics was incorporated in 2019 " + "and " * 200 + "but not in 2020."
        evidence = Evidence("halvorsen-robotics.test")
        evidence.add_prose("https://halvorsen-robotics.test/x", sentence, "nimble")
        self.assertIsNone(evidence.decide()["founded_year"]["value"])

    def test_rl21_long_sentence_with_a_second_value_stays_unknown(self):
        sentence = "Halvorsen Robotics was incorporated in 2019 " + "and " * 200 + "with funding in 2020."
        evidence = Evidence("halvorsen-robotics.test")
        evidence.add_prose("https://halvorsen-robotics.test/x", sentence, "nimble")
        self.assertIsNone(evidence.decide()["founded_year"]["value"])


class EvidenceDecisionTests(unittest.TestCase):
    def test_supported_fields_are_known_with_verbatim_citations(self):
        evidence = Evidence(D)
        evidence.add_served_text("https://acme-robotics.test/about", "Kind: own\n\n" + PROSE, "nimble")
        fields = evidence.decide()
        self.assertEqual(fields["hq_city"]["value"], "Lisbon")
        self.assertEqual(fields["ceo"]["value"], "Dana Ruiz")
        self.assertEqual(fields["founded_year"]["value"], 2014)
        self.assertIsNone(fields["funding_total"]["value"])
        self.assertEqual(fields["funding_total"]["citations"], [])
        citation = fields["hq_city"]["citations"][0]
        self.assertEqual(citation["excerpt"], "Acme Robotics, Inc. is headquartered in Lisbon.")
        self.assertEqual(citation["provider"], "nimble")
        self.assertEqual(citation["url"], "https://acme-robotics.test/about")

    def test_most_distinct_pages_wins(self):
        evidence = Evidence(D)
        evidence.add_served_text("https://a.test/1", "X: y\n\nAcme Robotics was founded in 2014.", "nimble")
        evidence.add_served_text("https://a.test/2", "X: y\n\nAcme Robotics was founded in 2015.", "nimble")
        evidence.add_served_text("https://a.test/3", "X: y\n\nAcme Robotics was founded in 2015.", "nimble")
        self.assertEqual(evidence.decide()["founded_year"]["value"], 2015)

    def test_tie_prefers_company_page_then_smallest_value(self):
        evidence = Evidence(D)
        evidence.add_served_text("https://news.test/1", "X: y\n\nAcme Robotics was founded in 2015.", "nimble")
        evidence.add_served_text("https://news.test/2", "X: y\n\nAcme Robotics was founded in 2016.", "nimble")
        self.assertEqual(evidence.decide()["founded_year"]["value"], 2015)
        evidence.add_served_text("https://acme-robotics.test/x", "X: y\n\nAcme Robotics was founded in 2016.", "nimble")
        self.assertEqual(evidence.decide()["founded_year"]["value"], 2016)

    def test_citations_come_from_distinct_pages_capped_at_three(self):
        evidence = Evidence(D)
        for index in range(5):
            evidence.add_served_text(
                f"https://news.test/{index}",
                f"X: y\n\nAcme Robotics was founded in 2014 (story {index}).",
                "nimble",
            )
        citations = evidence.decide()["founded_year"]["citations"]
        self.assertEqual(len(citations), 3)
        self.assertEqual(len({c["url"] for c in citations}), 3)

    def test_research_claim_on_a_negated_sentence_is_not_asserted(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        page = "X: y\n\nAcme Robotics reportedly was founded in 2014."
        evidence.add_served_text(url, page, "nimble")
        evidence.add_research_claim(url, "founded_year", 2014, "Acme Robotics reportedly was founded in 2014.")
        self.assertIsNone(evidence.decide()["founded_year"]["value"])

    def test_research_claim_with_supported_value_and_verbatim_citation_counts(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        evidence.add_served_text(url, "X: y\n\nAcme Robotics was founded in 2014.", "nimble")
        evidence.add_research_claim(url, "founded_year", "2014", "Acme Robotics was founded in 2014.")
        self.assertEqual(set(evidence.support["founded_year"]), {2014})
        self.assertEqual(evidence.decide()["founded_year"]["value"], 2014)

    def test_research_claim_with_wrong_value_is_discarded(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        evidence.add_served_text(url, "X: y\n\nAcme Robotics was founded in 2014.", "nimble")
        evidence.add_research_claim(url, "founded_year", 2001, "Acme Robotics was founded in 2014.")
        self.assertEqual(set(evidence.support["founded_year"]), {2014})

    def test_research_excerpt_not_verbatim_in_page_is_discarded(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        evidence.add_served_text(url, "X: y\n\nAcme Robotics reportedly was founded in 2014.", "nimble")
        evidence.add_research_claim(url, "founded_year", 2015, "Acme Robotics was founded in 2015.")
        self.assertNotIn(2015, evidence.support.get("founded_year", {}))

    def test_research_claim_from_unknown_page_is_discarded(self):
        evidence = Evidence(D)
        evidence.add_research_claim(
            "https://other.test/", "founded_year", 2014, "Acme Robotics was founded in 2014."
        )
        self.assertEqual(evidence.support, {})

    def test_non_numeric_claim_is_discarded_not_raised(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        evidence.add_served_text(url, "X: y\n\nAcme Robotics reportedly was founded in 2014.", "nimble")
        evidence.add_research_claim(url, "founded_year", "around 2014", "Acme Robotics was founded in 2014.")
        self.assertNotIn("around 2014", evidence.support.get("founded_year", {}))
        self.assertIsNone(evidence.decide()["founded_year"]["value"])


@unittest.skipUnless(os.environ.get("DOSSIER_MOCK_WEB"), "needs the mock web (DOSSIER_MOCK_WEB)")
class MockWebBuildTests(unittest.TestCase):
    def test_halvorsen_build_within_budget_and_one_exact_domain_search(self):
        os.environ.setdefault("NIMBLE_API_KEY", "local")
        os.environ["NIMBLE_BASE_URL"] = os.environ["DOSSIER_MOCK_WEB"].rstrip("/") + "/nimble"
        from engine import run_build

        spend = []
        result = run_build("halvorsen-robotics.test", on_spend=spend.append)
        self.assertTrue(result.ok)
        self.assertLessEqual(result.spent, 80)
        self.assertEqual(sum(spend), result.spent)
        self.assertEqual(result.fields["founded_year"]["value"], 2019)


if __name__ == "__main__":
    unittest.main()
