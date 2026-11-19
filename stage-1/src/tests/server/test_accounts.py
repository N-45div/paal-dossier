"""Login must not survive a reset that lands while its password check runs (R1.25, R1.143)."""

import unittest
from unittest import mock

from dossier.server import accounts
from dossier.server.errors import ApiError
from dossier.server.passwords import hash_password
from dossier.server.store import Store, User
from dossier.server.timestamps import parse_rfc3339

NOW = parse_rfc3339("2026-03-01T09:00:00+00:00")


def seeded_store() -> Store:
    store = Store()
    user = User("u_ada", "ada@example.com", "Ada", hash_password("correct horse"))
    store.replace_state(users=[user], tokens={}, dossiers=[], claims={}, instant=NOW)
    return store


class LoginRacesReset(unittest.TestCase):
    def test_reset_during_password_check_refuses_the_login(self):
        store = seeded_store()
        real_verify = accounts.verify_password

        def verify_then_reset(password, stored):
            result = real_verify(password, stored)
            store.replace_state(users=[], tokens={}, dossiers=[], claims={})  # empty fixture lands here
            return result

        with mock.patch.object(accounts, "verify_password", verify_then_reset):
            with self.assertRaises(ApiError) as raised:
                accounts.login(store, {"email": "ada@example.com", "password": "correct horse"})
        self.assertEqual(raised.exception.status, 401)
        self.assertEqual(store.tokens, {})

    def test_login_without_a_race_still_issues_a_token(self):
        store = seeded_store()
        session = accounts.login(store, {"email": "ADA@example.com", "password": "correct horse"})
        self.assertEqual(accounts.authenticate(store, f"Bearer {session.token}")[0], "u_ada")


if __name__ == "__main__":
    unittest.main()
