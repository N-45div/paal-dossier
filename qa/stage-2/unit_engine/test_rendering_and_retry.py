"""Unit tests for rendered-extract cost and 429 handling in engine/gateway.py (P5; R2.9, R2.10,
R2.30, RL60, RL61). Needs web_router: run with the builder venv's python, e.g.
  /home/ndivij/buildathon/band-work/venvs/builder-b/bin/python3 -I qa/stage-2/unit_engine/test_rendering_and_retry.py
"""

import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "stage-2"))

from engine import gateway as gateway_module  # noqa: E402
from engine.costs import RENDERED_EXTRACT_COST_PER_URL, charged_units  # noqa: E402
from engine.gateway import RENDER_OPTIONS, Gateway  # noqa: E402
from engine.ledger import Ledger  # noqa: E402


class RateLimited(Exception):
    """A provider answer of 429, as web_router reports it (kind rate_limit)."""

    kind = "rate_limit"
    status_code = 429


def bare_gateway(ledger):
    """A Gateway without a WebRouter: only the retry and settle paths are under test."""
    gw = Gateway.__new__(Gateway)
    gw._ledger = ledger
    gw._cancelled = None
    gw._lock = __import__("threading").Lock()
    gw._answered = 0
    return gw


class RenderedExtractTests(unittest.TestCase):
    def test_r2_10_rendered_extract_costs_three_units_a_url(self):
        self.assertEqual(RENDERED_EXTRACT_COST_PER_URL["nimble"], 3)

    def test_r2_10_render_option_is_passed_to_nimble(self):
        self.assertEqual(RENDER_OPTIONS, {"render": True})

    def test_rl60_reserve_extract_reserves_three_units(self):
        ledger = Ledger(budget=80)
        gw = bare_gateway(ledger)
        self.assertTrue(gw.reserve_extract())
        self.assertFalse(ledger.reserve(78))  # 3 of 80 are reserved for this URL
        self.assertTrue(ledger.reserve(77))
        self.assertFalse(Ledger(budget=2).reserve(3))

    def test_rl60_about_sixteen_rendered_urls_fit_after_domain_and_support_searches(self):
        ledger = Ledger(budget=80)
        self.assertTrue(ledger.reserve(25))  # research start
        self.assertTrue(ledger.reserve(1) and ledger.reserve(5))  # domain lite plus a support search
        granted = 0
        while ledger.reserve(3):
            granted += 1
        self.assertEqual(granted, 16)


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        patcher = mock.patch.object(gateway_module.time, "sleep", side_effect=self.sleeps.append)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rl61_429_costs_nothing(self):
        self.assertEqual(charged_units(RateLimited("slow down"), 1), 0)

    def test_rl61_retry_waits_at_least_one_point_oh_five_seconds(self):
        ledger = Ledger(budget=80)
        gw = bare_gateway(ledger)
        answers = [RateLimited("429"), RateLimited("429"), "ok"]
        answer, charged = gw._call_with_retry(1, lambda: _next(answers))
        self.assertEqual(answer, "ok")
        self.assertEqual(charged, 1)
        self.assertEqual(len(self.sleeps), 2)
        self.assertTrue(all(delay >= 1.05 for delay in self.sleeps), self.sleeps)

    def test_rl61_three_consecutive_429s_then_answer_is_tolerated(self):
        ledger = Ledger(budget=80)
        gw = bare_gateway(ledger)
        answers = [RateLimited("429")] * 3 + ["ok"]
        answer, charged = gw._call_with_retry(1, lambda: _next(answers))
        self.assertEqual((answer, charged), ("ok", 1))

    def test_rl61_a_call_that_stays_429_is_an_error_answer_costing_nothing(self):
        ledger = Ledger(budget=80)
        gw = bare_gateway(ledger)
        answer, charged = gw._call_with_retry(3, lambda: _raise(RateLimited("429")))
        self.assertIsNone(answer)
        self.assertEqual(charged, 0)
        self.assertEqual(len(self.sleeps), gateway_module.REFUSAL_ATTEMPTS - 1)


def _next(items):
    item = items.pop(0)
    if isinstance(item, BaseException):
        raise item
    return item


def _raise(error):
    raise error


if __name__ == "__main__":
    unittest.main()
