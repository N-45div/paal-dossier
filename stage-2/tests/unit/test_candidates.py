"""Candidate identity and the stage-1 outcome adapter (Rul-S2-1, Rul-S2-2)."""

import unittest

from app.candidates import Candidate, dedupe
from app.outcome import BuildOutcome, FieldResult, candidates_of, unknown_fields


class CandidateTest(unittest.TestCase):
    def test_identical_candidates_collapse_after_trimming_strings(self):
        first = Candidate(" Dana Ruiz ", "https://a.test/x", "Dana Ruiz leads.", "nimble", "own")
        second = Candidate("Dana Ruiz", "https://a.test/x", "Dana Ruiz leads.", "nimble", "own")
        self.assertEqual(dedupe([first, second]), [first])

    def test_different_provider_is_a_different_candidate(self):
        a = Candidate("Dana Ruiz", "https://a.test/x", "Dana Ruiz leads.", "nimble")
        b = Candidate("Dana Ruiz", "https://a.test/x", "Dana Ruiz leads.", "tavily")
        self.assertEqual(len(dedupe([a, b])), 2)

    def test_stage1_outcome_yields_one_candidate_per_citation(self):
        cite = {"url": "https://a.test/x", "excerpt": "Acme was founded in 2014.",
                "provider": "nimble"}
        fields = unknown_fields()
        fields["founded_year"] = FieldResult(2014, [cite])
        candidates = candidates_of(BuildOutcome(ok=True, spent_units=0, fields=fields))
        self.assertEqual(candidates["founded_year"],
                         [Candidate(2014, cite["url"], cite["excerpt"], "nimble")])
        self.assertEqual(candidates["ceo"], [])

    def test_explicit_candidates_are_used_as_given(self):
        cand = Candidate("Dana Ruiz", "https://a.test/x", "Dana Ruiz leads.", "nimble", "own")
        outcome = BuildOutcome(ok=True, spent_units=0, fields=unknown_fields(),
                               candidates={"ceo": [cand]})
        self.assertEqual(candidates_of(outcome)["ceo"], [cand])
        self.assertEqual(candidates_of(outcome)["hq_city"], [])


if __name__ == "__main__":
    unittest.main()
