"""Gateway budget rules with a fake router: refunds, charges, refusals and the call shape."""

import threading
import unittest
from types import SimpleNamespace

from web_router import ResearchTimeoutError

from dossier.engine.gateway import ERROR, OK, REFUSED, UNANSWERED, Gateway


class StatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class UrlFailure(SimpleNamespace):
    pass


class FakeRouter:
    """Records calls; `answer` is the object returned, or an exception instance raised."""

    def __init__(self, answer=None):
        self.answer = answer
        self.calls = []

    def _respond(self, name, kwargs):
        self.calls.append((name, kwargs))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer

    def search(self, query, **kwargs):
        return self._respond("search", {"query": query, **kwargs})

    def extract(self, urls, **kwargs):
        return self._respond("extract", {"urls": urls, **kwargs})

    def research(self, query, **kwargs):
        return self._respond("research", {"query": query, **kwargs})


def result(url, title="t", content="body text", description="snippet"):
    return SimpleNamespace(url=url, title=title, content=content, description=description)


class SearchRules(unittest.TestCase):
    def test_answered_search_keeps_its_cost_and_returns_full_text(self):
        router = FakeRouter(SimpleNamespace(results=[result("https://a.test/x", content="full page")]))
        gateway = Gateway(router=router)
        reply = gateway.search("a.test", depth="lite")
        self.assertEqual((reply.status, gateway.spent, gateway.any_success), (OK, 1, True))
        self.assertEqual(reply.items[0].text, "full page")
        self.assertEqual(router.calls[0][1]["search_depth"], "lite")

    def test_error_status_gives_the_reserve_back(self):
        gateway = Gateway(router=FakeRouter(StatusError(500)))
        reply = gateway.search("a.test", depth="deep")
        self.assertEqual((reply.status, gateway.spent), (ERROR, 0))

    def test_call_without_an_answer_keeps_its_cost(self):
        gateway = Gateway(router=FakeRouter(TimeoutError("read timed out")))
        reply = gateway.search("a.test", depth="fast")
        self.assertEqual((reply.status, gateway.spent), (UNANSWERED, 5))

    def test_budget_refuses_before_any_call(self):
        router = FakeRouter(SimpleNamespace(results=[]))
        gateway = Gateway(budget=10, router=router)
        self.assertEqual(gateway.search("a.test", depth="deep").status, REFUSED)
        self.assertEqual((gateway.spent, router.calls), (0, []))

    def test_results_are_capped_at_ten_and_render_is_never_set(self):
        router = FakeRouter(SimpleNamespace(results=[]))
        Gateway(router=router).search("a.test", max_results=50)
        kwargs = router.calls[0][1]
        self.assertEqual(kwargs["max_results"], 10)
        self.assertNotIn("render", str(kwargs.get("provider_options")))

    def test_cancelled_gateway_makes_no_call(self):
        cancel = threading.Event()
        cancel.set()
        router = FakeRouter(SimpleNamespace(results=[]))
        self.assertEqual(Gateway(router=router, cancel=cancel).search("a.test").status, REFUSED)
        self.assertEqual(router.calls, [])


class ExtractRules(unittest.TestCase):
    def test_missing_page_is_answered_and_keeps_its_cost(self):
        failure = UrlFailure(url="https://a.test/x", status_code=404)
        gateway = Gateway(router=FakeRouter(SimpleNamespace(documents=[], failures=[failure])))
        reply = gateway.extract(["https://a.test/x"])
        self.assertEqual((reply.status, gateway.spent, reply.items), (OK, 1, {"https://a.test/x": None}))

    def test_refused_url_is_refunded_and_answered_url_is_kept(self):
        doc = SimpleNamespace(url="https://a.test/ok", title="ok", content="page")
        failure = UrlFailure(url="https://a.test/bad", status_code=500)
        gateway = Gateway(router=FakeRouter(SimpleNamespace(documents=[doc], failures=[failure])))
        reply = gateway.extract(["https://a.test/ok", "https://a.test/bad"])
        self.assertEqual((reply.status, gateway.spent), (OK, 1))
        self.assertEqual(reply.items["https://a.test/ok"].text, "page")
        self.assertIsNone(reply.items["https://a.test/bad"])

    def test_error_status_on_the_whole_call_refunds_every_url(self):
        gateway = Gateway(router=FakeRouter(StatusError(429)))
        self.assertEqual(gateway.extract(["https://a.test/1", "https://a.test/2"]).status, ERROR)
        self.assertEqual(gateway.spent, 0)

    def test_tavily_extract_costs_two_per_url(self):
        gateway = Gateway(router=FakeRouter(SimpleNamespace(documents=[], failures=[])))
        gateway.extract(["https://a.test/1"], provider="tavily")
        self.assertEqual(gateway.spent, 2)


class ResearchRules(unittest.TestCase):
    def test_claims_need_a_mapped_field_with_a_citation(self):
        response = SimpleNamespace(
            structured={"ceo": "Dana Ruiz", "founded_year": 2014, "hq_city": None},
            citations=[
                SimpleNamespace(url="https://a.test/about", snippet="Dana Ruiz leads it.", field="$.ceo"),
                SimpleNamespace(url="https://a.test/x", snippet="Founded in 2014.", field="$.founded_year"),
                SimpleNamespace(url="https://a.test/y", snippet="Other.", field="$.unknown_field"),
                SimpleNamespace(url="https://a.test/z", snippet="No path.", field=None),
            ],
        )
        gateway = Gateway(router=FakeRouter(response))
        reply = gateway.research("a.test")
        self.assertEqual(reply.status, OK)
        self.assertEqual([(c.field, c.value) for c in reply.items], [("ceo", "Dana Ruiz"), ("founded_year", 2014)])
        self.assertEqual(gateway.spent, 25)

    def test_research_timeout_keeps_the_run_cost(self):
        gateway = Gateway(router=FakeRouter(ResearchTimeoutError("nimble", "job-1", 60)))
        reply = gateway.research("a.test")
        self.assertEqual((reply.status, gateway.spent), (UNANSWERED, 25))

    def test_research_error_status_refunds_the_run(self):
        gateway = Gateway(router=FakeRouter(StatusError(500)))
        self.assertEqual(gateway.research("a.test").status, ERROR)
        self.assertEqual(gateway.spent, 0)


if __name__ == "__main__":
    unittest.main()
