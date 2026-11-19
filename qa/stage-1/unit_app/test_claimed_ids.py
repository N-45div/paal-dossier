"""Traceability: each claimed ledger id maps to named tests (or to a documented gap).

Entries are "Class.method" names in the modules listed in MODULES. A test fails if a named
test does not exist, or if a claimed id has no entry. "manual:" entries are verified by the
docker smoke run recorded in the handoff; "gap:" entries are declared gaps with a reason.
"""

import importlib
import unittest

MODULES = ["test_foundation", "test_domain", "test_dossiers", "test_precision_and_limits", "test_import_validation"]

P1_IDS = [6, 7, 8, 11, 12, 14, 15, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
          48, 49, 50, 51, 53, 54, 56, 57, 58, 59, 63, 64, 65, 66, 67, 68, 69, 70, 124, 125, 126, 127, 128]
P3_IDS = [40, 52, 55, 60, 61] + list(range(71, 86)) + list(range(89, 110))

COVERAGE = {
    # P1 foundation
    6: ["manual: docker build and run per RUN.md, smoke recorded in handoff"],
    7: ["manual: docker build and run per RUN.md, smoke recorded in handoff"],
    8: ["manual: docker run with -e PORT and a port mapping, smoke recorded in handoff"],
    11: ["manual: Dockerfile pip install line, image contains webrouter"],
    12: ["gap: provider variables are read by the engine (P4); P1 reads PORT only"],
    14: ["manual: container limits measured with docker stats (222 MiB, 2 vCPU cap)"],
    15: ["manual: health reachable within seconds of container start (smoke)"],
    16: ["manual: 50 concurrent logins measured (smoke, 0.16 s)"],
    17: ["PrecisionTests.test_R1_17_two_thousand_user_fixture_resets_within_budget"],
    19: ["manual: state held in memory, container restart clears it (RUN.md)"],
    20: ["gap: no runtime assets in P1; nothing to include"],
    21: ["manual: app/__main__.py binds 0.0.0.0 at PORT (smoke)"],
    22: ["FoundationTests.test_health_is_ok_without_auth"],
    23: ["FoundationTests.test_reset_clears_previous_accounts",
         "FoundationTests.test_reset_rejects_duplicate_email_without_changing_state"],
    24: ["PrecisionTests.test_R1_24_and_R1_26_clock_moves_only_on_reset_or_clock_and_stands_still"],
    25: ["PrecisionTests.test_R1_25_before_first_reset_the_clock_follows_system_time"],
    26: ["PrecisionTests.test_R1_24_and_R1_26_clock_moves_only_on_reset_or_clock_and_stands_still"],
    27: ["PrecisionTests.test_R1_27_nine_digit_fractions_compare_exactly",
         "PrecisionTests.test_R1_27_offsets_out_of_range_are_rejected",
         "FoundationTests.test_clock_rejects_earlier_time_and_offsets_are_required"],
    28: ["FoundationTests.test_clock_rejects_earlier_time_and_offsets_are_required"],
    29: ["PrecisionTests.test_R1_29_responses_are_json_utf8_and_ascii_escaped"],
    30: ["gap: timestamps use format_ts (explicit offset); no test asserts the output string yet"],
    31: ["FoundationTests.test_unknown_fields_are_ignored"],
    32: ["FoundationTests.test_unknown_fields_are_ignored"],
    33: ["PrecisionTests.test_R1_33_counter_is_bounded_so_ids_stay_within_64_characters"],
    34: ["FoundationTests.test_seeded_user_logs_in_with_given_password",
         "FoundationTests.test_signup_then_duplicate_email_is_409"],
    35: ["DomainTests.test_invalid_hosts_are_422", "DomainTests.test_equivalent_spellings_normalise_to_one_domain"],
    36: ["DomainTests.test_equivalent_spellings_normalise_to_one_domain"],
    48: ["FoundationTests.test_reset_rejects_duplicate_email_without_changing_state",
         "Ruling16FixtureTests.test_fixture_user_field_rules"],
    49: ["FoundationTests.test_envelope_on_unknown_route_and_method"],
    50: ["FoundationTests.test_envelope_on_unknown_route_and_method"],
    51: ["FoundationTests.test_wrong_json_type_is_400_and_missing_field_is_422"],
    53: ["FoundationTests.test_missing_or_unknown_bearer_token_is_401"],
    54: ["FoundationTests.test_envelope_on_unknown_route_and_method"],
    56: ["FoundationTests.test_signup_validation"],
    57: ["FoundationTests.test_signup_validation"],
    58: ["DossierTests.test_list_rejects_bad_integers"],
    59: ["DossierTests.test_list_rejects_bad_integers"],
    63: ["FoundationTests.test_seeded_user_logs_in_with_given_password"],
    64: ["FoundationTests.test_signup_then_duplicate_email_is_409"],
    65: ["FoundationTests.test_signup_validation", "FoundationTests.test_wrong_password_and_unknown_email_are_401"],
    66: ["FoundationTests.test_seeded_user_logs_in_with_given_password"],
    67: ["FoundationTests.test_missing_or_unknown_bearer_token_is_401"],
    68: ["FoundationTests.test_missing_or_unknown_bearer_token_is_401"],
    69: ["FoundationTests.test_export_import_round_trip_keeps_tokens_and_accounts"],
    70: ["FoundationTests.test_export_import_round_trip_keeps_tokens_and_accounts"],
    124: ["FoundationTests.test_export_import_round_trip_keeps_tokens_and_accounts"],
    125: ["FoundationTests.test_export_import_round_trip_keeps_tokens_and_accounts",
          "ImportValidationTests.test_fresh_reset_export_is_itself_a_valid_import"],
    126: ["FoundationTests.test_invalid_import_is_422_and_changes_nothing",
          "FoundationTests.test_import_is_replacement_and_repeatable",
          "ImportValidationTests.test_empty_object_state_is_rejected",
          "ImportValidationTests.test_non_object_state_and_missing_state_are_422",
          "ImportValidationTests.test_missing_section_or_extra_section_is_rejected"],
    127: ["FoundationTests.test_export_import_round_trip_keeps_tokens_and_accounts",
          "DossierTests.test_export_import_keeps_dossiers_and_idempotent_replay"],
    128: ["DossierTests.test_export_of_building_dossier_is_its_last_completed_state"],
    # P3 dossier API
    40: ["DossierTests.test_build_becomes_ready_with_fields_and_spend"],
    52: ["DossierTests.test_missing_or_empty_key_is_400_and_long_key_is_422"],
    55: ["DossierTests.test_same_key_different_body_is_409"],
    60: ["DossierTests.test_missing_or_empty_key_is_400_and_long_key_is_422"],
    61: ["DossierTests.test_list_rejects_bad_integers"],
    71: ["DossierTests.test_same_key_on_different_path_is_independent"],
    72: ["gap: cross-user key independence is not unit tested; prover acceptance covers it"],
    73: ["DossierTests.test_same_key_on_different_path_is_independent"],
    74: ["DossierTests.test_missing_or_empty_key_is_400_and_long_key_is_422"],
    75: ["DossierTests.test_first_open_is_202_and_replay_is_200_with_same_body"],
    76: ["DossierTests.test_first_open_is_202_and_replay_is_200_with_same_body"],
    77: ["DossierTests.test_same_key_different_body_is_409"],
    78: ["DossierTests.test_failed_4xx_does_not_claim_key"],
    79: ["DossierTests.test_replay_survives_unknown_field_changes_but_invalid_body_is_409"],
    80: ["DossierTests.test_concurrent_identical_opens_create_one_dossier"],
    81: ["DossierTests.test_export_import_keeps_dossiers_and_idempotent_replay"],
    82: ["DossierTests.test_replay_survives_unknown_field_changes_but_invalid_body_is_409"],
    83: ["DossierTests.test_refresh_is_404_without_dossier_and_202_with_one"],
    84: ["gap: a second refresh while a build runs is not unit tested; the handler checks state under the lock"],
    85: ["DossierTests.test_failed_build_leaves_fields_unknown"],
    89: ["gap: reads make no provider call is not unit tested; the read handlers do not touch the engine"],
    90: ["DossierTests.test_open_requires_bearer_before_key_check"],
    91: ["DossierTests.test_first_open_is_202_and_replay_is_200_with_same_body"],
    92: ["DossierTests.test_first_open_is_202_and_replay_is_200_with_same_body"],
    93: ["DossierTests.test_concurrent_identical_opens_create_one_dossier"],
    94: ["DossierTests.test_read_normalises_path_and_404s_unknown", "DossierTests.test_failed_4xx_does_not_claim_key"],
    95: ["DossierTests.test_build_becomes_ready_with_fields_and_spend"],
    96: ["DossierTests.test_build_becomes_ready_with_fields_and_spend"],
    97: ["DossierTests.test_failed_build_leaves_fields_unknown"],
    98: ["DossierTests.test_build_becomes_ready_with_fields_and_spend"],
    99: ["DossierTests.test_build_becomes_ready_with_fields_and_spend"],
    100: ["DossierTests.test_read_normalises_path_and_404s_unknown"],
    101: ["DossierTests.test_refresh_is_404_without_dossier_and_202_with_one"],
    102: ["DossierTests.test_refresh_is_404_without_dossier_and_202_with_one"],
    103: ["DossierTests.test_refresh_is_404_without_dossier_and_202_with_one"],
    104: ["DossierTests.test_refresh_is_404_without_dossier_and_202_with_one"],
    105: ["DossierTests.test_list_filters_orders_and_pages"],
    106: ["DossierTests.test_list_filters_orders_and_pages"],
    107: ["DossierTests.test_list_filters_orders_and_pages"],
    108: ["DossierTests.test_list_filters_orders_and_pages"],
    109: ["DossierTests.test_list_filters_orders_and_pages"],
}

_CLASSES = {
    "FoundationTests": "test_foundation",
    "Ruling16FixtureTests": "test_foundation",
    "DomainTests": "test_domain",
    "DossierTests": "test_dossiers",
    "PrecisionTests": "test_precision_and_limits",
    "ImportValidationTests": "test_import_validation",
}


class ClaimedIdTraceabilityTests(unittest.TestCase):
    def test_every_claimed_id_has_an_entry(self):
        missing = [i for i in P1_IDS + P3_IDS if i not in COVERAGE]
        self.assertEqual(missing, [])

    def test_every_named_test_exists(self):
        for ident, entries in COVERAGE.items():
            for entry in entries:
                if entry.startswith(("manual:", "gap:")):
                    continue
                with self.subTest(ident=ident, entry=entry):
                    cls_name, method = entry.split(".")
                    module = importlib.import_module(_CLASSES[cls_name])
                    self.assertTrue(hasattr(getattr(module, cls_name), method), entry)

    def test_each_gap_states_a_reason(self):
        for ident, entries in COVERAGE.items():
            for entry in entries:
                if entry.startswith("gap:"):
                    self.assertGreater(len(entry), len("gap: "), f"id {ident} gap has no reason")


if __name__ == "__main__":
    unittest.main()
