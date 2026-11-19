"""Gateway budget rules with a fake router: refunds, charges, refusals and the call shape."""

import threading
import unittest
from types import SimpleNamespace

from web_router import ConfigurationError, ResearchTimeoutError

from dossier.engine.gateway import Gateway
from dossier.engine.providers import ERROR, OK, SKIPPED, TIMEOUT


class StatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class FakeRouter:
    """Records calls; `answer` is returned, or raised when it is an exception."""

    def __init__(self, answer=None):
        self.answer = answer
        self.calls = []

    def _respond(self, name, args, kwargs):
        self.calls.append((name, args, kwargs))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer

    def search(self, query, **kwargs):
        return self._respond("search", (query,), kwargs)

    def extract(self, urls, **kwargs):
        return self._respond("extract", (urls,), kwargs)

    def research(self, query, **kwargs):
        return self._respond("research", (query,), kwargs)


def result(url, content="body text", description="snippet"):
    return SimpleNamespace(url=url, title="t", content=content, description=description)


def failure(url, status_code):
    return SimpleNamespace(url=url, status_code=status_code)


class SearchRules(unittest.TestCase):
    def test_answered_search_keeps_its_cost_and_returns_full_text(self):
        router = FakeRouter(SimpleNamespace(results=[result("https://a.test/x", content="full page")]))
        gateway = Gateway(router=router)
        answer = gateway.search("a.test", "nimble", "lite")
        self.assertEqual((answer.status, gateway.spent, gateway.any_success), (OK, 1, True))
        self.assertEqual(answer.items[0].text, "full page")
        self.assertEqual(router.calls[0][2]["search_depth"], "lite")

    def test_error_status_gives_the_reserve_back(self):
        gateway = Gateway(router=FakeRouter(StatusError(500)))
        self.assertEqual(gateway.search("a.test", "nimble", "deep").status, ERROR)
        self.assertEqual(gateway.spent, 0)

    def test_call_without_an_answer_keeps_its_cost(self):
        gateway = Gateway(router=FakeRouter(TimeoutError("read timed out")))
        self.assertEqual(gateway.search("a.test", "nimble", "fast").status, TIMEOUT)
        self.assertEqual(gateway.spent, 5)

    def test_missing_credential_is_skipped_and_costs_nothing(self):
        gateway = Gateway(router=FakeRouter(ConfigurationError("No API key for provider 'nimble'.")))
        self.assertEqual(gateway.search("a.test", "nimble", "deep").status, SKIPPED)
        self.assertEqual(gateway.spent, 0)

    def test_budget_skips_before_any_call(self):
        router = FakeRouter(SimpleNamespace(results=[]))
        gateway = Gateway(budget=10, router=router)
        self.assertEqual(gateway.search("a.test", "nimble", "deep").status, SKIPPED)
        self.assertEqual((gateway.spent, router.calls), (0, []))

    def test_can_call_is_advisory_and_respects_the_budget(self):
        gateway = Gateway(budget=10, router=FakeRouter())
        self.assertTrue(gateway.can_call(10))
        self.assertFalse(gateway.can_call(11))
        self.assertEqual(gateway.spent, 0)

    def test_results_are_capped_at_ten_and_render_is_never_set(self):
        router = FakeRouter(SimpleNamespace(results=[]))
        Gateway(router=router).search("a.test", "nimble", "lite")
        kwargs = router.calls[0][2]
        self.assertEqual(kwargs["max_results"], 10)
        self.assertNotIn("render", str(kwargs.get("provider_options")))

    def test_cancelled_gateway_makes_no_call(self):
        cancel = threading.Event()
        cancel.set()
        router = FakeRouter(SimpleNamespace(results=[]))
        self.assertEqual(Gateway(router=router, cancel=cancel).search("a.test", "nimble", "lite").status, SKIPPED)
        self.assertEqual(router.calls, [])


class ExtractRules(unittest.TestCase):
    def test_missing_page_is_answered_and_keeps_its_cost(self):
        gateway = Gateway(router=FakeRouter(SimpleNamespace(documents=[], failures=[failure("https://a.test/x", 404)])))
        answer = gateway.extract(["https://a.test/x"])
        self.assertEqual((answer.status, gateway.spent, answer.items), (OK, 1, ()))

    def test_refused_url_is_refunded_and_served_page_is_returned(self):
        doc = SimpleNamespace(url="https://a.test/ok", title="ok", content="page")
        gateway = Gateway(router=FakeRouter(SimpleNamespace(documents=[doc], failures=[failure("https://a.test/bad", 500)])))
        answer = gateway.extract(["https://a.test/ok", "https://a.test/bad"])
        self.assertEqual((answer.status, gateway.spent), (OK, 1))
        self.assertEqual([(page.url, page.text) for page in answer.items], [("https://a.test/ok", "page")])

    def test_error_status_on_the_whole_call_refunds_every_url(self):
        gateway = Gateway(router=FakeRouter(StatusError(429)))
        self.assertEqual(gateway.extract(["https://a.test/1", "https://a.test/2"]).status, ERROR)
        self.assertEqual(gateway.spent, 0)


class ResearchRules(unittest.TestCase):
    def test_claims_need_a_mapped_requested_field_with_a_citation(self):
        response = SimpleNamespace(
            structured={"ceo": "Dana Ruiz", "founded_year": 2014, "hq_city": None},
            citations=[
                SimpleNamespace(url="https://a.test/about", snippet="Dana Ruiz leads it.", field="$.ceo"),
                SimpleNamespace(url="https://a.test/x", snippet="Founded in 2014.", field="$.founded_year"),
                SimpleNamespace(url="https://a.test/y", snippet="Other.", field="$.unknown_field"),
                SimpleNamespace(url="https://a.test/z", snippet="No path.", field=None),
            ],
        )
        router = FakeRouter(response)
        gateway = Gateway(router=router)
        answer = gateway.research("a.test", ["ceo", "founded_year"])
        self.assertEqual(answer.status, OK)
        self.assertEqual([(c.field, c.value) for c in answer.items], [("ceo", "Dana Ruiz"), ("founded_year", 2014)])
        self.assertEqual(gateway.spent, 25)
        self.assertEqual(sorted(router.calls[0][2]["output_schema"]["properties"]), ["ceo", "founded_year"])

    def test_research_timeout_keeps_the_run_cost(self):
        gateway = Gateway(router=FakeRouter(ResearchTimeoutError("nimble", "job-1", 60)))
        self.assertEqual(gateway.research("a.test", ["ceo"]).status, TIMEOUT)
        self.assertEqual(gateway.spent, 25)

    def test_research_error_status_refunds_the_run(self):
        gateway = Gateway(router=FakeRouter(StatusError(500)))
        self.assertEqual(gateway.research("a.test", ["ceo"]).status, ERROR)
        self.assertEqual(gateway.spent, 0)


if __name__ == "__main__":
    unittest.main()
