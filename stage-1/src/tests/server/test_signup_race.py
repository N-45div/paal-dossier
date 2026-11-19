"""Two signups for one email across a reset (R1.79, R1.143).

Each test pauses the first signup inside password hashing, runs the other step at that exact
point, then lets the first signup finish. The outcomes must match a serial order.
"""

import unittest
from unittest import mock

from dossier.server import accounts
from dossier.server.errors import ApiError
from dossier.server.store import Store
from dossier.server.timestamps import parse_rfc3339

NOW = parse_rfc3339("2026-03-01T09:00:00+00:00")
FORM = {"email": "same@example.com", "password": "long enough", "display_name": "Same"}


def empty_store() -> Store:
    store = Store()
    store.replace_state(users=[], tokens={}, dossiers=[], claims={}, instant=NOW)
    return store


def hashing_hook(during):
    """Patch hash_password so that `during()` runs once, while the first caller is hashing."""
    real = accounts.hash_password
    pending = [during]

    def hash_then(password):
        digest = real(password)
        if pending:
            pending.pop()()
        return digest

    return mock.patch.object(accounts, "hash_password", hash_then)


class TwoSignupsAcrossAReset(unittest.TestCase):
    def test_duplicate_during_hashing_is_409_and_the_first_is_not_lost(self):
        """Serial order: A, then B (409), then the reset. A's 201 is answered, nothing survives."""
        store = empty_store()
        outcomes = {}

        def second_signup_while_first_hashes():
            try:
                accounts.signup(store, FORM)
                outcomes["second"] = "201"
            except ApiError as error:
                outcomes["second"] = error.code

        with hashing_hook(second_signup_while_first_hashes):
            first = accounts.signup(store, FORM)
        store.replace_state(users=[], tokens={}, dossiers=[], claims={})
        self.assertEqual(outcomes["second"], "email_taken")
        self.assertIsNotNone(first.token)
        self.assertEqual((store.users, store.tokens), ({}, {}))

    def test_reset_between_two_signups_keeps_only_the_later_one(self):
        """Serial order: A (reset lands while hashing, so A is discarded), reset, then B (201, stored)."""
        store = empty_store()

        def reset_and_signup_again():
            store.replace_state(users=[], tokens={}, dossiers=[], claims={})
            accounts.signup(store, FORM)

        with hashing_hook(reset_and_signup_again):
            first = accounts.signup(store, FORM)
        self.assertEqual(len(store.users), 1)  # B's user survives; A's does not
        self.assertNotIn(first.token, store.tokens)
        self.assertEqual(list(store.user_by_email), ["same@example.com"])


if __name__ == "__main__":
    unittest.main()
