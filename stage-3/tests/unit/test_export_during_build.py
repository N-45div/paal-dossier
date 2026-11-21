"""Rul-7: an export taken while a build runs holds the state before that build (ready with its
records), and the durable document keeps the running flag so a build cut short loads as failed
(Rul-S3-2). These run on State and persist directly, with no HTTP."""

from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timezone

from app.persist import state_from, state_json
from app.snapshot import export_state, import_state
from app.state import Dossier, State
from tests.unit.test_history import URL_A, T1, ready

DOMAIN = "acme.test"


def _state_building() -> State:
    """A dossier with one completed ready build, and a second build running."""
    state = State()
    dossier = Dossier(id="d1", domain=DOMAIN, last_outcome="ready")
    dossier.records = [ready(0, T1, {URL_A: (date(2026, 1, 10), {"ceo": ["Dana Ruiz"]})})]
    dossier.building = True
    state.dossiers_by_domain[DOMAIN] = dossier
    return state


class ExportDuringBuildTest(unittest.TestCase):

    def test_export_imports_as_the_last_completed_ready_build(self):
        raw = json.loads(json.dumps(export_state(_state_building())))
        restored = import_state(raw).dossiers_by_domain[DOMAIN]
        self.assertFalse(restored.building)
        self.assertEqual(restored.last_outcome, "ready")
        self.assertEqual(len(restored.records), 1)
        self.assertTrue(restored.records[0].ok)

    def test_export_of_a_dossier_that_never_completed_is_failed_not_building(self):
        state = State()
        state.dossiers_by_domain[DOMAIN] = Dossier(id="d1", domain=DOMAIN, building=True)
        restored = import_state(json.loads(json.dumps(export_state(state)))).dossiers_by_domain[DOMAIN]
        self.assertFalse(restored.building)
        self.assertEqual(restored.last_outcome, "failed")
        self.assertEqual(restored.records, [])

    def test_durable_document_keeps_the_running_flag(self):
        # A stop mid-build: the durable document still says building, and loads as failed.
        raw = json.loads(json.dumps(state_json(_state_building())))
        restored = state_from(raw).dossiers_by_domain[DOMAIN]
        self.assertFalse(restored.building)
        self.assertEqual(restored.last_outcome, "failed")
        self.assertEqual(len(restored.records), 1)
