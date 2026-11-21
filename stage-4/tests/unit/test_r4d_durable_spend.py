"""R4D (stage 4, Rul-S4-4, Rul-S4-6, R4.62-R4.68): spend is written durably at once, so a stop keeps
every billed unit; a build left running ends failed on load with its spend counted; a batch with all
its builds ended is done. Runs on State and persist directly, with no HTTP."""

from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timezone

from app.budget import SharedBudget
from app.builds import _BuildSpend, _spend_recorder
from app.persist import state_from, state_json
from app.state import Batch, Dossier, State, Store
from tests.unit.test_history import T1, URL_A, ready

DOMAIN = "acme.test"


class CountingPersister:
    def __init__(self) -> None:
        self.saves = 0

    def save(self, state, fixed) -> None:
        self.saves += 1


class FixedClock:
    fixed = None


def _store_with_dossier(building: bool) -> tuple[Store, Dossier, CountingPersister]:
    persister = CountingPersister()
    store = Store(FixedClock(), persister)
    dossier = Dossier(id="d1", domain=DOMAIN, building=building, last_outcome="ready")
    dossier.records = [ready(0, T1, {URL_A: (date(2026, 1, 1), {"ceo": ["Dana Ruiz"]})})]
    store.state.dossiers_by_domain[DOMAIN] = dossier
    return store, dossier, persister


class SpendIsWrittenAtOnceTest(unittest.TestCase):

    def test_each_billed_change_is_saved_and_counted(self):
        store, dossier, persister = _store_with_dossier(building=True)
        spend = _BuildSpend()
        on_spend = _spend_recorder(store, dossier, store.state.generation, spend)
        on_spend(5)
        on_spend(-2)
        self.assertEqual((dossier.spent_units, spend.total), (3, 3))
        self.assertEqual(persister.saves, 2)

    def test_a_replaced_state_is_neither_counted_nor_saved(self):
        store, dossier, persister = _store_with_dossier(building=True)
        spend = _BuildSpend()
        on_spend = _spend_recorder(store, dossier, store.state.generation - 1, spend)
        on_spend(5)
        self.assertEqual((dossier.spent_units, spend.total, persister.saves), (0, 0, 0))


class RestartTest(unittest.TestCase):

    def test_a_build_left_running_loads_failed_with_its_spend_counted(self):
        store, dossier, _ = _store_with_dossier(building=True)
        dossier.spent_units = 30
        restored = state_from(json.loads(json.dumps(state_json(store.state))))
        loaded = restored.dossiers_by_domain[DOMAIN]
        self.assertFalse(loaded.building)
        self.assertEqual(loaded.last_outcome, "failed")
        self.assertEqual(loaded.spent_units, 30)

    def test_batch_spend_survives_and_a_batch_with_no_running_build_is_done(self):
        store, dossier, _ = _store_with_dossier(building=True)
        dossier.spent_units = 30
        batch = Batch(id="b_1", user_id="u1", budget=SharedBudget(100, 40), domains=[DOMAIN], started=[DOMAIN])
        store.state.batches[batch.id] = batch
        restored = state_from(json.loads(json.dumps(state_json(store.state))))
        loaded = restored.batches["b_1"]
        self.assertEqual(loaded.budget.spent, 40)
        self.assertFalse(restored.dossiers_by_domain[DOMAIN].building)  # so the batch reads done
