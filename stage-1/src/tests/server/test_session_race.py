"""Forced interleavings: state changes (reset, import) while a request is in flight.

Each test runs one request, then fires the state change at the exact point where the
request has read or verified its state and not yet written it. The request must not leave
anything behind in the new state (R1.25, R1.143, lead ruling on reset and import generation).
"""

import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from dossier.server import accounts, builds, snapshot, routes
from dossier.server.errors import ApiError
from dossier.server.model import Build, Dossier
from dossier.server.passwords import hash_password
from dossier.server.service import Service
from dossier.server.store import Store, User
from dossier.server.timestamps import parse_rfc3339
from fake_engine import FakeEngine, result

NOW = parse_rfc3339("2026-03-01T09:00:00+00:00")


class Harness(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        user = User("u_ada", "ada@example.com", "Ada", hash_password("correct horse"))
        self.store.replace_state(users=[user], tokens={}, dossiers=[], claims={}, instant=NOW)
        self.engine = FakeEngine(result(ok=True, spent=5))
        self.service = Service(self.store, self.engine, ThreadPoolExecutor(max_workers=2))
        self.token = accounts.login(self.store, {"email": "ada@example.com", "password": "correct horse"}).token

    def tearDown(self):
        self.service.executor.shutdown(wait=True)

    def wipe(self, **extra):
        """A reset to an empty fixture, or an import with the given parts."""
        self.store.replace_state(users=[], tokens={}, dossiers=[], claims={}, **extra)

    def fire_after_authentication(self, state_change):
        real = accounts.authenticate

        def authenticate_then_change(store, authorization):
            result_ = real(store, authorization)
            state_change()
            return result_

        return mock.patch.object(accounts, "authenticate", authenticate_then_change)

    def fire_after_authentication_of(self, state_change):
        return self.fire_after_authentication(state_change)

    def wait_until_idle(self, domain):
        import time

        for _ in range(500):
            with self.store.lock:
                if self.store.dossiers[domain].build is None:
                    return
            time.sleep(0.01)
        self.fail("build did not finish")

    def assert_empty(self):
        self.assertEqual((self.store.users, self.store.dossiers, self.store.claims), ({}, {}, {}))

    def dispatch(self, method, path, body=b"", key=None):
        return routes.dispatch(self.service, method, path, f"Bearer {self.token}", key, body)


class AuthenticatedWritesAndReads(Harness):
    def test_dossier_create_refused_and_writes_nothing(self):
        with self.fire_after_authentication(self.wipe):
            with self.assertRaises(ApiError) as raised:
                self.dispatch("POST", "/dossiers", b'{"domain": "acme.test"}', key="race-create")
        self.assertEqual(raised.exception.status, 401)
        self.assert_empty()
        self.assertEqual(self.engine.calls, [])

    def test_refresh_refused_and_starts_no_build(self):
        self.dispatch("POST", "/dossiers", b'{"domain": "acme.test"}', key="first")
        self.wait_until_idle("acme.test")
        calls_before = len(self.engine.calls)
        with self.fire_after_authentication(self.wipe):
            with self.assertRaises(ApiError) as raised:
                self.dispatch("POST", "/dossiers/acme.test/refresh", key="race-refresh")
        self.assertEqual(raised.exception.status, 401)
        self.assert_empty()
        self.assertEqual(len(self.engine.calls), calls_before)

    def test_read_refused_after_reset(self):
        self.dispatch("POST", "/dossiers", b'{"domain": "acme.test"}', key="first")
        with self.fire_after_authentication(self.wipe):
            with self.assertRaises(ApiError) as raised:
                self.dispatch("GET", "/dossiers/acme.test")
        self.assertEqual(raised.exception.status, 401)

    def test_idempotent_replay_refused_after_reset(self):
        self.dispatch("POST", "/dossiers", b'{"domain": "acme.test"}', key="replay-me")
        with self.fire_after_authentication(self.wipe):
            with self.assertRaises(ApiError) as raised:
                self.dispatch("POST", "/dossiers", b'{"domain": "acme.test"}', key="replay-me")
        self.assertEqual(raised.exception.status, 401)  # not a 200 replay of the old response
        self.assert_empty()

    def test_import_during_request_leaves_only_the_imported_state(self):
        self.dispatch("POST", "/dossiers", b'{"domain": "old.test"}', key="old")
        self.wait_until_idle("old.test")
        document = snapshot.export_document(self.store)  # the state holding Ada's token and old.test
        imported = snapshot.load_document(document)
        with self.fire_after_authentication(lambda: self.store.replace_state(
            users=imported.users, tokens=imported.tokens, dossiers=imported.dossiers, claims=imported.claims)):
            with self.assertRaises(ApiError) as raised:
                self.dispatch("POST", "/dossiers", b'{"domain": "acme.test"}', key="race-import")
        self.assertEqual(raised.exception.status, 401)
        self.assertEqual(set(self.store.dossiers), {"old.test"})  # the import's state, nothing more


class SignupAndBuilds(Harness):
    def test_signup_straddling_a_reset_leaves_no_user_or_token(self):
        real_hash = accounts.hash_password

        def hash_then_reset(password):
            digest = real_hash(password)
            self.wipe()
            return digest

        with mock.patch.object(accounts, "hash_password", hash_then_reset):
            session = accounts.signup(self.store, {"email": "new@example.com", "password": "long enough", "display_name": "New"})
        self.assertNotIn(session.token, self.store.tokens)
        self.assertEqual(self.store.users, {})
        self.assertEqual(self.store.user_by_email, {})

    def test_build_finishing_after_a_reset_changes_nothing(self):
        stale = Build("acme.test", NOW, generation=self.store.generation)
        self.wipe()
        fresh = Dossier(dossier_id="d_new", domain="acme.test")
        self.store.dossiers["acme.test"] = fresh
        builds._finish(self.store, stale, builds.Outcome(True, 9, {}))
        self.assertIs(self.store.dossiers["acme.test"], fresh)
        self.assertEqual((fresh.spent_units, fresh.state), (0, "failed"))


if __name__ == "__main__":
    unittest.main()
