"""R3.21: `selected` is true on the highest-ranked candidate of each title that has candidates,
and false on the others. Six-field candidates keep the first ranked one as selected. Runs on
field_json directly, with no HTTP."""

from __future__ import annotations

import unittest

from app.candidates import Candidate
from app.dossiers import field_json
from app.history import Selected


def _cand(value: str, title: str | None, url: str) -> Candidate:
    return Candidate(value=value, url=url, excerpt=value, provider="nimble", kind="own",
                     title=title)


def _selected_flags(view: Selected) -> list[bool]:
    return [c["selected"] for c in field_json(view, None)["candidates"]]


class SelectedFlagsTest(unittest.TestCase):

    def test_executives_flags_the_top_candidate_of_each_title(self):
        # Ranked: cfo's two candidates, then coo, then cto. Three titles, so three selected.
        ranked = (
            (_cand("Petra Garrow", "cfo", "https://a.test/1"), None),
            (_cand("Ana Silva", "cfo", "https://a.test/2"), None),
            (_cand("Mirela Ellery", "coo", "https://a.test/3"), None),
            (_cand("Lucas Beaumont", "cto", "https://a.test/4"), None),
        )
        view = Selected(field="executives", value=[{"title": "cfo", "name": "Petra Garrow"}],
                        status="contested", true_from=None, learned_at=None, citations=(),
                        ranked=ranked)
        self.assertEqual(_selected_flags(view), [True, False, True, True])

    def test_six_field_flags_only_the_first_ranked_candidate(self):
        ranked = (
            (_cand("Acme Robotics Inc", None, "https://a.test/1"), None),
            (_cand("Acme Robotics", None, "https://a.test/2"), None),
        )
        view = Selected(field="legal_name", value="Acme Robotics Inc", status="known",
                        true_from=None, learned_at=None, citations=(), ranked=ranked)
        self.assertEqual(_selected_flags(view), [True, False])

    def test_executives_with_no_candidates_has_no_flags(self):
        view = Selected(field="executives", value=None, status="unknown", true_from=None,
                        learned_at=None, citations=(), ranked=())
        self.assertEqual(_selected_flags(view), [])
