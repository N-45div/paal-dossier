"""An idempotent write and its exportable claim are one step (R1.139, R1.143).

The POST (or refresh) is paused inside its critical section, after the dossier and the build are
in place. An export started then must wait, and must contain both the dossier and the completed
claim. An import of that export must replay the original 202 body under the same key.
"""

import json
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from dossier.server import accounts, builds, routes, snapshot
from dossier.server.passwords import hash_password
from dossier.server.service import Service
from dossier.server.store import Store, User
from dossier.server.timestamps import parse_rfc3339
from fake_engine import FakeEngine, result

NOW = parse_rfc3339("2026-03-01T09:00:00+00:00")


class PausedWrite(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        user = User("u_ada", "ada@example.com", "Ada", hash_password("correct horse"))
        self.store.replace_state(users=[user], tokens={}, dossiers=[], claims={}, instant=NOW)
        self.service = Service(self.store, FakeEngine(result(ok=True, spent=5)), ThreadPoolExecutor(max_workers=2))
        self.token = accounts.login(self.store, {"email": "ada@example.com", "password": "correct horse"}).token

    def tearDown(self):
        self.service.executor.shutdown(wait=True)

    def pause_inside_the_write(self):
        """Hold the write right after start_build, still inside its critical section."""
        real_start = builds.start_build
        inside, go = threading.Event(), threading.Event()

        def start_then_hold(service, dossier):
            real_start(service, dossier)
            inside.set()
            go.wait(timeout=10)

        return mock.patch.object(builds, "start_build", start_then_hold), inside, go

    def run_write(self, method, path, body, key, results):
        results["write"] = routes.dispatch(self.service, method, path, f"Bearer {self.token}", key, body)

    def test_export_during_a_paused_dossier_post_contains_the_dossier_and_its_claim(self):
        patch, inside, go = self.pause_inside_the_write()
        results = {}
        with patch:
            writer = threading.Thread(target=self.run_write, args=("POST", "/dossiers", b'{"domain": "acme.test"}', "k-post", results))
            writer.start()
            self.assertTrue(inside.wait(timeout=5))
            exported = {}
            exporter = threading.Thread(target=lambda: exported.__setitem__("doc", snapshot.export_document(self.store)))
            exporter.start()
            time.sleep(0.2)
            self.assertTrue(exporter.is_alive(), "export must wait for the write in progress")
            go.set()
            writer.join(timeout=10)
            exporter.join(timeout=10)

        status, body = results["write"]
        self.assertEqual(status, 202)
        state = exported["doc"]["state"]
        self.assertEqual([d["domain"] for d in state["dossiers"]], ["acme.test"])
        self.assertEqual([c["key"] for c in state["claims"]], ["k-post"])  # never the dossier without its claim

        # the import of that export replays the original body under the same key
        fresh = Store()
        fresh_service = Service(fresh, FakeEngine(), ThreadPoolExecutor(max_workers=1))
        loaded = snapshot.load_document(json.loads(json.dumps(exported["doc"])))
        fresh.replace_state(users=loaded.users, tokens=loaded.tokens, dossiers=loaded.dossiers, claims=loaded.claims)
        # Ada's token is part of the export, so it authenticates in the imported state too
        replay_status, replay = routes.dispatch(fresh_service, "POST", "/dossiers", f"Bearer {self.token}", "k-post", b'{"domain": "acme.test"}')
        fresh_service.executor.shutdown(wait=True)
        self.assertEqual((replay_status, replay), (200, body))  # the original 'building' body

    def test_export_during_a_paused_refresh_contains_the_refresh_claim(self):
        self.run_write("POST", "/dossiers", b'{"domain": "acme.test"}', "first", {})
        while True:
            with self.store.lock:
                if self.store.dossiers["acme.test"].build is None:
                    break
            time.sleep(0.01)
        patch, inside, go = self.pause_inside_the_write()
        results = {}
        with patch:
            writer = threading.Thread(target=self.run_write, args=("POST", "/dossiers/acme.test/refresh", None, "k-refresh", results))
            writer.start()
            self.assertTrue(inside.wait(timeout=5))
            exported = {}
            exporter = threading.Thread(target=lambda: exported.__setitem__("doc", snapshot.export_document(self.store)))
            exporter.start()
            time.sleep(0.2)
            self.assertTrue(exporter.is_alive())
            go.set()
            writer.join(timeout=10)
            exporter.join(timeout=10)
        self.assertEqual(results["write"][0], 202)
        self.assertIn("k-refresh", [c["key"] for c in exported["doc"]["state"]["claims"]])


if __name__ == "__main__":
    unittest.main()
