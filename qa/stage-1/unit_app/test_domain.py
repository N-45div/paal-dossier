"""Domain normalisation (R1.35–R1.36).

Index of claimed ids covered in this module:
    R1.35 -> DomainTests.test_equivalent_spellings_normalise_to_one_domain
    R1.35 -> DomainTests.test_invalid_hosts_are_422
    R1.36 -> DomainTests.test_equivalent_spellings_normalise_to_one_domain
"""

import unittest

from app.domain import normalise_domain
from app.errors import ApiError


class DomainTests(unittest.TestCase):
    def test_equivalent_spellings_normalise_to_one_domain(self):
        """Covers R1.35, R1.36."""
        for raw in ["Acme-Robotics.TEST.", "www.acme-robotics.test", "  acme-robotics.test  "]:
            self.assertEqual(normalise_domain(raw), "acme-robotics.test")

    def test_invalid_hosts_are_422(self):
        """Covers R1.35."""
        for raw in ["localhost", "https://acme.test", "acme.test/path", "a..test", "-a.test", "a-.test", "a_b.test", "", "a." * 130 + "test"]:
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(ApiError) as caught:
                    normalise_domain(raw)
                self.assertEqual(caught.exception.status, 422)


if __name__ == "__main__":
    unittest.main()
