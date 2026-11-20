"""Unit tests for stage-2/engine/pages.py: Kind and Published parsing (R2.5-R2.8).

Provider-free. Run: python3 -I qa/stage-2/unit_engine/test_pages.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "stage-2"))

from engine.pages import default_kind, page_kind, parse_kind, parse_published  # noqa: E402

DOMAIN = "acme-robotics.test"


class KindTests(unittest.TestCase):
    def test_r2_6_the_four_kinds_match_exactly(self):
        for kind in ("own", "filing", "news", "aggregator"):
            self.assertEqual(parse_kind(kind), kind)

    def test_r2_6_other_values_are_not_kinds(self):
        for value in ("Own", " own", "own ", "blog", "", None):
            self.assertIsNone(parse_kind(value))

    def test_r2_8_default_rule_no_line_on_company_host_is_own(self):
        self.assertEqual(page_kind(None, "https://acme-robotics.test/about", DOMAIN), "own")
        self.assertEqual(page_kind(None, "https://www.acme-robotics.test/about", DOMAIN), "own")
        self.assertEqual(page_kind(None, "https://press.acme-robotics.test/x", DOMAIN), "own")

    def test_r2_8_default_rule_no_line_off_company_host_is_aggregator(self):
        self.assertEqual(page_kind(None, "https://bizdata.test/acme-robotics", DOMAIN), "aggregator")
        self.assertEqual(default_kind("https://notacme-robotics.test/x", DOMAIN), "aggregator")

    def test_r2_8_unlisted_kind_value_takes_the_default_rule(self):
        self.assertEqual(page_kind("blog", "https://bizdata.test/x", DOMAIN), "aggregator")
        self.assertEqual(page_kind("Filing", "https://acme-robotics.test/x", DOMAIN), "own")

    def test_r2_6_listed_kind_overrides_the_default_rule(self):
        self.assertEqual(page_kind("news", "https://acme-robotics.test/x", DOMAIN), "news")
        self.assertEqual(page_kind("filing", "https://registry.test/x", DOMAIN), "filing")


class PublishedTests(unittest.TestCase):
    def test_r2_7_valid_rfc3339_timestamps_are_kept_as_written(self):
        for value in (
            "2026-01-10T00:00:00+00:00",
            "2026-01-10T00:00:00Z",
            "2026-01-10T12:30:59.123+05:30",
            "2024-02-29T23:59:59-00:00",
            "2026-01-10T00:00:00.1234567890123Z",
        ):
            self.assertEqual(parse_published(value), value)

    def test_rl66_lowercase_t_and_z_are_accepted(self):
        self.assertEqual(parse_published("2026-01-10t00:00:00+00:00"), "2026-01-10t00:00:00+00:00")
        self.assertEqual(parse_published("2026-01-10T00:00:00z"), "2026-01-10T00:00:00z")

    def test_r2_7_basic_format_is_refused(self):
        self.assertIsNone(parse_published("20260110T000000+00:00"))
        self.assertIsNone(parse_published("20260110T000000Z"))

    def test_r2_7_space_separator_is_refused(self):
        self.assertIsNone(parse_published("2026-01-10 00:00:00+00:00"))

    def test_r2_7_offset_or_zone_is_required(self):
        self.assertIsNone(parse_published("2026-01-10T00:00:00"))
        self.assertIsNone(parse_published("2026-01-10"))

    def test_rl66_leap_second_is_accepted(self):
        self.assertEqual(parse_published("2016-12-31T23:59:60Z"), "2016-12-31T23:59:60Z")

    def test_r2_7_leap_instant_past_year_9999_has_no_time_rl70(self):
        self.assertIsNone(parse_published("9999-12-31T23:59:60Z"))
        self.assertIsNone(parse_published("9999-12-31T23:59:60+00:00"))
        self.assertIsNone(parse_published("9999-12-31T18:59:60-05:00"))
        self.assertEqual(parse_published("9999-12-31T23:59:59Z"), "9999-12-31T23:59:59Z")

    def test_r2_7_midday_leap_second_is_not_a_timestamp_rl70(self):
        self.assertIsNone(parse_published("2016-12-31T12:30:60Z"))

    def test_r2_7_offset_equivalent_of_utc_23_59_60_is_accepted_rl70(self):
        self.assertEqual(parse_published("2016-12-31T18:59:60-05:00"), "2016-12-31T18:59:60-05:00")
        self.assertEqual(parse_published("2017-01-01T00:29:60+00:30"), "2017-01-01T00:29:60+00:30")

    def test_r2_7_out_of_range_fields_are_refused(self):
        self.assertIsNone(parse_published("2026-13-01T00:00:00Z"))
        self.assertIsNone(parse_published("2026-02-30T00:00:00Z"))
        self.assertIsNone(parse_published("2025-02-29T00:00:00Z"))
        self.assertIsNone(parse_published("2026-01-10T24:00:00Z"))
        self.assertIsNone(parse_published("2026-01-10T00:60:00Z"))
        self.assertIsNone(parse_published("2026-01-10T00:00:61Z"))
        self.assertIsNone(parse_published("2026-01-10T00:00:00+24:00"))
        self.assertIsNone(parse_published("2026-01-10T00:00:00+05:60"))

    def test_r2_7_absent_or_empty_value_has_no_time(self):
        self.assertIsNone(parse_published(None))
        self.assertIsNone(parse_published(""))
        self.assertIsNone(parse_published("yesterday"))


if __name__ == "__main__":
    unittest.main()
