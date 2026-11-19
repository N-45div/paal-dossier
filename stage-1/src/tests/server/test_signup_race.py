"""Two signups for one email across a reset (R1.79, R1.143).

Each test holds the first signup inside password hashing, runs the other step while it is held,
then releases it. The outcomes must match a serial order.
"""

import threading
import time
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


def hash_gate(once_then):
    """Patch hash_password so that `once_then()` runs once, while the first caller is hashing."""
    real = accounts.hash_password
    pending = [once_then]

    def gated(password):
        digest = real(password)
        if pending:
            pending.pop()()
        return digest

    return mock.patch.object(accounts, "hash_password", gated)


class TwoSignupsAcrossAReset(unittest.TestCase):
    def test_duplicate_waits_for_the_in_flight_signup_then_sees_it_committed(self):
        """Serial order: A, then B (409). B's 409 must not be answered before A is committed."""
        store = empty_store()
        release = threading.Event()
        first_hashing = threading.Event()
        real = accounts.hash_password

        def hold_first(password):
            first_hashing.set()
            release.wait(timeout=10)
            return real(password)

        results = {}
        with mock.patch.object(accounts, "hash_password", hold_first):
            first = threading.Thread(target=lambda: results.__setitem__("first", accounts.signup(store, FORM)))
            first.start()
            self.assertTrue(first_hashing.wait(timeout=5))

            def second():
                try:
                    accounts.signup(store, FORM)
                    results["second"] = "201"
                except ApiError as error:
                    results["second"] = error.code

            second_thread = threading.Thread(target=second)
            second_thread.start()
            time.sleep(0.2)
            self.assertTrue(second_thread.is_alive(), "the duplicate must wait, not answer 409 early")
            self.assertNotIn("second", results)
            release.set()
            first.join(timeout=10)
            second_thread.join(timeout=10)

        self.assertEqual(results["second"], "email_taken")
        self.assertEqual(len(store.users), 1)  # A is committed before B's 409 is answered
        self.assertEqual(accounts.login(store, {"email": FORM["email"], "password": FORM["password"]}).user_id,
                         results["first"].user_id)

    def test_reset_between_two_signups_keeps_only_the_later_one(self):
        """Serial order: A (reset lands while hashing, so A is discarded), reset, then B (201, stored)."""
        store = empty_store()

        def reset_and_signup_again():
            store.replace_state(users=[], tokens={}, dossiers=[], claims={})
            accounts.signup(store, FORM)

        with hash_gate(once_then=reset_and_signup_again):
            first = accounts.signup(store, FORM)
        self.assertEqual(len(store.users), 1)  # B's user survives; A's does not
        self.assertNotIn(first.token, store.tokens)
        self.assertEqual(list(store.user_by_email), ["same@example.com"])


if __name__ == "__main__":
    unittest.main()
