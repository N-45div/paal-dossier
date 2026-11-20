# Acceptance claims and verbatim ledger entries

Source: Stage 1 ledger at lead revision `f3d0e3c89ff0cf14f4a9a8c24c7ba5a6af638538`. Each referenced test names the ID; a reference is not a claim that every subclause has been fully verified. Optional call types and live-only requirements remain conditional. RL24 amends the funding_total range; RL25–RL50 were issued as binding room rulings after that ledger revision.

Not claimed by individual tests: R1.1, R1.6, R1.10, R1.11, R1.13, R1.19, R1.88.

### R1.2
- Section: 1. Scope
- Spec lines: 16-16
- Package: all / prover
- Status: open
- Text:

  > The following apply to all operations, including concurrent requests and retries:

Referenced tests: `test_api.py::test_R1_2_R1_16_R1_17_R1_62_R1_80_R1_93_R1_129_concurrent_identical`

### R1.3
- Section: 1. Scope
- Spec lines: 18-20
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > 1. Every value the service asserts cites at least one excerpt that a provider endpoint served
  >    to this service, and that excerpt supports the value. No citation is invented, reworded, or
  >    attached to a value it does not support.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_state_faults.py::test_R1_3_R1_40_R1_43_RL29_fallback_citation_provider_is_actual_server`, `test_synthetic.py::test_R1_3_R1_41_R1_43_R1_86_dual_provider_texts_at_one_url`, `test_synthetic.py::test_R1_44_R1_155_R1_164_large_amount_exact`, `test_synthetic.py::test_R1_3_R1_43_R1_44_citation_length_limit`, `test_synthetic.py::test_R1_3_R1_43_R1_86_long_sentence_supporting_prefix`

### R1.4
- Section: 1. Scope
- Spec lines: 21-21
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > 2. No build of a dossier spends more than 80 units (§9).

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.5
- Section: 1. Scope
- Spec lines: 23-23
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > Contact data, people search, and fields other than the six in §4 are out of scope.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.7
- Section: 2. Delivery and deployment
- Spec lines: 31-35
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > The submission is a containerized HTTP service, not a Python package. Python is not
  > required in the implementation. TypeScript/JavaScript, Go, Rust, Java, Python and any
  > other language are equally valid. The submitted `Dockerfile` is built and started,
  > and only its HTTP behavior is exercised; it does not import or execute the
  > submission's source files on the host that runs it.

Referenced tests: `test_api.py::test_R1_15_R1_21_R1_22_R1_49_health`

### R1.8
- Section: 2. Delivery and deployment
- Spec lines: 37-39
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > The image must run on its own with `-e PORT=<port>` and a port mapping. All runtime
  > dependencies, initialization and seed data must work within that single container. Compose
  > configuration is not used to start the service.

Referenced tests: `test_api.py::test_R1_15_R1_21_R1_22_R1_49_health`

### R1.9
- Section: Web access
- Spec lines: 43-46
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > Two providers are available: `nimble` and `tavily`. Nimble is the default provider: every
  > service must be able to research companies using Nimble alone. Tavily is optional: a service
  > may use it beside Nimble, and its absence must not prevent research while Nimble answers.
  > The live submission and optional live judging provide a working Nimble key only.

Referenced tests: `test_state_faults.py::test_R1_9_R1_62_R1_85_provider_errors`, `test_state_faults.py::test_R1_9_tavily_failure_does_not_prevent_nimble`, `test_state_faults.py::test_R1_9_R1_62_R1_85_nimble_failure`

### R1.12
- Section: Web access
- Spec lines: 60-68
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > The deployment provides these environment variables:
  >
  > | Variable | Meaning |
  > |---|---|
  > | `PORT` | The port to listen on (§3.1) |
  > | `NIMBLE_API_KEY` | Credential for the `nimble` provider |
  > | `NIMBLE_BASE_URL` | Base URL of the `nimble` provider endpoint |
  > | `TAVILY_API_KEY` | Credential for the `tavily` provider |
  > | `TAVILY_BASE_URL` | Base URL of the `tavily` provider endpoint |

Referenced tests: `test_api.py::test_R1_15_R1_21_R1_22_R1_49_health`

### R1.14
- Section: Resource limits
- Spec lines: 84-85
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > | CPU | 2 vCPU |
  > | Memory | 3 GiB |

Referenced tests: `test_api.py::test_R1_14_container_memory_limit`

### R1.15
- Section: Resource limits
- Spec lines: 86-86
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > | Start to first healthy response | 60 s |

Referenced tests: `test_api.py::test_R1_15_R1_21_R1_22_R1_49_health`

### R1.16
- Section: Resource limits
- Spec lines: 87-87
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > | Concurrent requests | up to 50 in flight |

Referenced tests: `test_api.py::test_R1_2_R1_16_R1_17_R1_62_R1_80_R1_93_R1_129_concurrent_identical`, `test_api.py::test_R1_16_R1_55_R1_62_R1_77_R1_80_R1_129_concurrent_conflicting`, `test_api.py::test_R1_16_R1_17_R1_62_R1_65_R1_69_R1_129_concurrent_signup`, `test_api.py::test_R1_16_R1_17_R1_62_R1_69_concurrent_logins`, `test_api.py::test_R1_16_R1_62_R1_93_R1_129_concurrent_different_keys`

### R1.17
- Section: Resource limits
- Spec lines: 88-88
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > | Per-request timeout | 5 s (10 s for `POST /_test/reset`) |

Referenced tests: `test_api.py::test_R1_2_R1_16_R1_17_R1_62_R1_80_R1_93_R1_129_concurrent_identical`, `test_api.py::test_R1_16_R1_17_R1_62_R1_65_R1_69_R1_129_concurrent_signup`, `test_api.py::test_R1_16_R1_17_R1_62_R1_69_concurrent_logins`, `test_foundation.py::test_R1_17_R1_23_R1_48_500_seeded_users`, `test_foundation.py::test_R1_17_R1_70_R1_126_RL27_import_rejects_other_scrypt_parameters`, `test_foundation.py::test_R1_17_R1_23_R1_31_body_size_boundary`

### R1.18
- Section: Resource limits
- Spec lines: 89-89
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Outbound network | available during `docker build`; at run time, **only the provider endpoints this specification lists** |

Referenced tests: `test_api.py::test_R1_15_R1_21_R1_22_R1_49_health`, `test_synthetic.py::test_R1_18_RL13_extract_concurrency_at_most_eight`

### R1.20
- Section: Resource limits
- Spec lines: 92-94
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Runtime assets and dependencies must be included in the image. This includes fonts,
  > scripts and stylesheets; external services other than the provider endpoints this
  > specification lists are unavailable at runtime.

Referenced tests: `test_api.py::test_R1_15_R1_21_R1_22_R1_49_health`

### R1.21
- Section: 3.1 Listening
- Spec lines: 100-100
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Listen on `0.0.0.0` using the `PORT` environment variable, default `8080`.

Referenced tests: `test_api.py::test_R1_15_R1_21_R1_22_R1_49_health`

### R1.22
- Section: 3.2 Health
- Spec lines: 108-110
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Return 200 once the service and its data store can serve requests, within 60 seconds
  > of container start. Non-200 responses are permitted before the service is ready.
  > `/health` makes no provider call.

Referenced tests: `test_api.py::test_R1_15_R1_21_R1_22_R1_49_health`

### R1.23
- Section: 3.3 Reset and seed
- Spec lines: 123-127
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Replace all service state with the fixture in the request body (§4). When reset returns
  > 204, subsequent requests must see only that fixture: no users other than the seeded ones,
  > no dossiers and no stored idempotent responses. Repeated resets are supported. A build
  > still running when reset is called must not change the state that follows the reset.
  > This control endpoint must be enabled in the delivered image and requires no authentication.

Referenced tests: `test_api.py::test_R1_23_R1_48_R1_63_R1_65_R1_66_R1_69_auth_reset`, `test_foundation.py::test_R1_23_R1_48_R1_63_R1_66_seed_and_reset`, `test_foundation.py::test_R1_23_R1_34_R1_48_R1_66_fixture_values_and_import`, `test_foundation.py::test_R1_23_R1_33_R1_48_fixture_validation_atomic`, `test_foundation.py::test_R1_23_R1_48_missing_fixture_field`, `test_foundation.py::test_R1_23_R1_48_fixture_duplicate_ids_atomic`, `test_foundation.py::test_R1_23_R1_25_reset_can_move_clock_backwards`, `test_foundation.py::test_R1_17_R1_23_R1_48_500_seeded_users`, `test_foundation.py::test_R1_17_R1_23_R1_31_body_size_boundary`, `test_state_faults.py::test_R1_23_R1_84_R1_128_reset_during_build`, `test_state_faults.py::test_R1_23_R1_67_R1_93_R1_129_reset_races_authenticated_opens`, `test_state_faults.py::test_R1_23_R1_67_R1_129_reset_races_authenticated_reads`

### R1.24
- Section: 3.4 Clock
- Spec lines: 131-132
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > The service keeps a clock that only reset and `POST /_test/clock` move. Every timestamp
  > the service records or returns is read from this clock.

Referenced tests: `test_api.py::test_R1_24_R1_25_R1_26_R1_27_R1_28_clock`, `test_foundation.py::test_R1_24_R1_25_R1_27_R1_28_clock_public_and_monotonic`

### R1.25
- Section: 3.4 Clock
- Spec lines: 143-144
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - Reset sets the clock to the fixture's `now`. Before the first reset the clock follows the
  >   system time.

Referenced tests: `test_api.py::test_R1_24_R1_25_R1_26_R1_27_R1_28_clock`, `test_foundation.py::test_R1_24_R1_25_R1_27_R1_28_clock_public_and_monotonic`, `test_foundation.py::test_R1_23_R1_25_reset_can_move_clock_backwards`, `test_foundation.py::test_R1_25_R1_27_RL26_leap_seconds`, `test_foundation.py::test_R1_25_R1_27_RL27_last_year_leap_second_is_out_of_range`, `test_foundation.py::test_R1_25_R1_27_RL18_fraction_comparison_exact_through_1000_digits`, `test_foundation.py::test_R1_25_R1_27_R1_85_R1_96_RL27_boundary_offset_build_completes`, `test_foundation.py::test_R1_25_R1_27_RL27_unrepresentable_utc_offset_rejected_atomically`, `test_foundation.py::test_R1_25_R1_27_long_fractional_timestamp`

### R1.26
- Section: 3.4 Clock
- Spec lines: 145-146
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - The clock stands still between calls: two requests with no clock call between them read
  >   the same time.

Referenced tests: `test_api.py::test_R1_24_R1_25_R1_26_R1_27_R1_28_clock`

### R1.27
- Section: 3.4 Clock
- Spec lines: 147-148
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - `now` is an RFC 3339 timestamp with an explicit offset. A `now` earlier than the clock's
  >   current time is 422 `validation_failed` and changes nothing.

Referenced tests: `test_api.py::test_R1_24_R1_25_R1_26_R1_27_R1_28_clock`, `test_foundation.py::test_R1_24_R1_25_R1_27_R1_28_clock_public_and_monotonic`, `test_foundation.py::test_R1_27_fractional_clock_precision`, `test_foundation.py::test_R1_25_R1_27_RL26_leap_seconds`, `test_foundation.py::test_R1_25_R1_27_RL27_last_year_leap_second_is_out_of_range`, `test_foundation.py::test_R1_25_R1_27_RL18_fraction_comparison_exact_through_1000_digits`, `test_foundation.py::test_R1_25_R1_27_R1_85_R1_96_RL27_boundary_offset_build_completes`, `test_foundation.py::test_R1_25_R1_27_RL27_unrepresentable_utc_offset_rejected_atomically`, `test_foundation.py::test_R1_27_invalid_rfc3339_offsets`, `test_foundation.py::test_R1_25_R1_27_long_fractional_timestamp`

### R1.28
- Section: 3.4 Clock
- Spec lines: 149-149
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - `POST /_test/clock` requires no authentication.

Referenced tests: `test_api.py::test_R1_24_R1_25_R1_26_R1_27_R1_28_clock`, `test_foundation.py::test_R1_24_R1_25_R1_27_R1_28_clock_public_and_monotonic`

### R1.29
- Section: 3.5 Conventions
- Spec lines: 153-153
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - Requests and responses are `application/json; charset=utf-8`.

Referenced tests: `test_api.py::test_R1_29_R1_30_json_and_timestamp`

### R1.30
- Section: 3.5 Conventions
- Spec lines: 154-154
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - Timestamps in responses are RFC 3339 with an explicit offset, e.g. `2026-09-24T19:00:00+02:00`.

Referenced tests: `test_api.py::test_R1_29_R1_30_json_and_timestamp`

### R1.31
- Section: 3.5 Conventions
- Spec lines: 155-155
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - Unknown fields in a request body are ignored, never an error.

Referenced tests: `test_api.py::test_R1_31_R1_33_R1_64_signup_extra_fields`, `test_api.py::test_R1_31_R1_35_R1_36_R1_92_R1_100_normalisation`, `test_foundation.py::test_R1_17_R1_23_R1_31_body_size_boundary`, `test_foundation.py::test_R1_31_R1_49_RL28_oversize_body_has_413_envelope`, `test_foundation.py::test_R1_31_RL28_small_chunked_body_is_parsed`, `test_foundation.py::test_R1_31_R1_49_RL49_malformed_chunk_framing_is_atomic`, `test_foundation.py::test_R1_31_RL49_chunk_extension_and_trailer_are_parsed`, `test_foundation.py::test_R1_31_R1_49_RL42_unframed_request_has_no_body_and_service_stays_healthy`, `test_foundation.py::test_R1_31_R1_49_RL30_keepalive_recovers_after_oversize`, `test_foundation.py::test_R1_31_R1_62_R1_64_R1_127_surrogate_round_trip`

### R1.32
- Section: 3.5 Conventions
- Spec lines: 156-156
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - Unknown query parameters are ignored.

Referenced tests: `test_api.py::test_R1_32_R1_34_R1_105_R1_107_R1_108_R1_109_order_and_pagination`

### R1.33
- Section: 3.5 Conventions
- Spec lines: 157-157
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - IDs are opaque strings of at most 64 characters. Their format is yours.

Referenced tests: `test_api.py::test_R1_31_R1_33_R1_64_signup_extra_fields`, `test_foundation.py::test_R1_23_R1_33_R1_48_fixture_validation_atomic`, `test_foundation.py::test_R1_33_R1_125_R1_126_RL20_max_counter_export_after_signup_round_trips`

### R1.34
- Section: Users
- Spec lines: 163-163
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Users sign up and log in (§6). Every authenticated user sees the same dossiers.

Referenced tests: `test_api.py::test_R1_32_R1_34_R1_105_R1_107_R1_108_R1_109_order_and_pagination`, `test_foundation.py::test_R1_23_R1_34_R1_48_R1_66_fixture_values_and_import`

### R1.35
- Section: Domains
- Spec lines: 167-172
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > A company is identified by its domain. Every domain the API takes, in a body or a path, is
  > first **normalised**: surrounding whitespace removed, lowercased, one trailing `.` removed,
  > and one leading `www.` removed. The normalised domain must then be a valid host name: two or
  > more labels separated by `.`, each label 1 to 63 characters of `a-z`, `0-9` and `-`, not
  > starting or ending with `-`, and 253 characters or fewer in total. Anything else, including a
  > URL with a scheme or a path, is 422 `validation_failed`.

Referenced tests: `test_api.py::test_R1_35_R1_51_R1_57_R1_94_invalid_domains`, `test_api.py::test_R1_31_R1_35_R1_36_R1_92_R1_100_normalisation`

### R1.36
- Section: Domains
- Spec lines: 174-175
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > `Acme-Robotics.TEST.`, `www.acme-robotics.test` and `acme-robotics.test` name the same
  > company and the same dossier. Responses always carry the normalised domain.

Referenced tests: `test_api.py::test_R1_31_R1_35_R1_36_R1_92_R1_100_normalisation`

### R1.37
- Section: Fields
- Spec lines: 179-179
- Package: all / prover
- Status: open
- Text:

  > A dossier has exactly these six fields:

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.38
- Section: Fields
- Spec lines: 183-188
- Package: all / prover
- Status: open
- Text:

  > | `legal_name` | String: the company's registered name, e.g. `Acme Robotics, Inc.` |
  > | `hq_city` | String: the city of the company's headquarters, without region or country, e.g. `Lisbon` |
  > | `ceo` | String: the full name of the company's chief executive, e.g. `Dana Ruiz` |
  > | `founded_year` | Integer: the year the company was founded, e.g. `2014` |
  > | `headcount_range` | String: one of `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+` |
  > | `funding_total` | Integer: total equity funding raised, in whole US dollars, e.g. `12000000` |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_synthetic.py::test_R1_38_R1_40_R1_126_invalid_import_field_values`

### R1.39
- Section: Fields
- Spec lines: 190-192
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > A string value is written as the supporting excerpt writes it, without surrounding
  > whitespace. A headcount the web states as a number, or as a range that fits inside one of
  > the ranges above, has the range that contains it as its value.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.40
- Section: Fields
- Spec lines: 194-207
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > Each field in a response has this shape:
  >
  > ```json
  > { "value": "Dana Ruiz", "status": "known",
  >   "citations": [ { "url": "https://acme-robotics.test/about",
  >                    "excerpt": "Dana Ruiz has led Acme Robotics as chief executive since 2021.",
  >                    "provider": "nimble" } ] }
  > ```
  >
  > - `status` is `known` when `value` is not null, and `unknown` when it is.
  > - A `known` field has one or more citations. An `unknown` field has `"value": null` and
  >   `"citations": []`.
  > - `url` is the URL of the page the excerpt was served for, `provider` is `nimble` or
  >   `tavily`, the provider that served it.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_state_faults.py::test_R1_3_R1_40_R1_43_RL29_fallback_citation_provider_is_actual_server`, `test_synthetic.py::test_R1_40_R1_45_R1_86_R1_126_research_zero_is_known_and_importable`, `test_synthetic.py::test_R1_40_R1_126_R1_127_invalid_dossier_snapshot_is_atomic`, `test_synthetic.py::test_R1_38_R1_40_R1_126_invalid_import_field_values`, `test_synthetic.py::test_R1_40_R1_43_R1_126_invalid_import_citation`

### R1.41
- Section: Evidence and support
- Spec lines: 211-213
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > The **evidence** for a company is every page that some search, through any provider and for
  > any query naming the company (as in Appendix A.2), returns, with its full text, and every
  > claim that a `nimble` research run for the company asking for all six fields answers with.

Referenced tests: `test_evidence.py::test_R1_41_R1_45_R1_86_cross_company_and_research_evidence`, `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_synthetic.py::test_R1_3_R1_41_R1_43_R1_86_dual_provider_texts_at_one_url`, `test_synthetic.py::test_R1_41_R1_43_R1_86_RL25_evidence_uses_mock_served_variant`, `test_synthetic.py::test_R1_41_R1_45_R1_86_unsearchable_page_only_claimed_field`

### R1.42
- Section: Evidence and support
- Spec lines: 215-218
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > Of the searches that a provider answers without an error, every build makes exactly one whose
  > query is exactly the company's normalised domain, through a provider of its choice; its other
  > such searches use other queries. A search that a provider answers with an error does not
  > count. The pages whose text a build obtains from providers are the pages it **gathers**.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_synthetic.py::test_R1_42_exact_domain_search_once`, `test_synthetic.py::test_R1_42_R1_62_retry_refused_nimble_domain_search`

### R1.43
- Section: Evidence and support
- Spec lines: 220-224
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > A **citation** is an excerpt of text a provider served for the page at `url`:
  >
  > - The excerpt is copied character for character from that served text, except that any run
  >   of whitespace may be written as a single space. It is 1 to 500 characters long.
  > - It is taken from the page's prose (below), not from its header.

Referenced tests: `test_evidence.py::test_R1_43_R1_44_R1_133_long_sentence_full_support`, `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_state_faults.py::test_R1_3_R1_40_R1_43_RL29_fallback_citation_provider_is_actual_server`, `test_synthetic.py::test_R1_3_R1_41_R1_43_R1_86_dual_provider_texts_at_one_url`, `test_synthetic.py::test_R1_41_R1_43_R1_86_RL25_evidence_uses_mock_served_variant`, `test_synthetic.py::test_R1_44_R1_155_R1_164_large_amount_exact`, `test_synthetic.py::test_R1_3_R1_43_R1_44_citation_length_limit`, `test_synthetic.py::test_R1_3_R1_43_R1_86_long_sentence_supporting_prefix`, `test_synthetic.py::test_R1_43_R1_44_R1_86_long_sentence_full_context`, `test_synthetic.py::test_R1_40_R1_43_R1_126_invalid_import_citation`

### R1.44
- Section: Evidence and support
- Spec lines: 226-230
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > An excerpt **supports** a value when, read on its own, it states that value for that field
  > of this company, as Appendix A defines. The excerpt may write the value differently from the
  > API: `Acme Robotics has raised $12M.` and `Acme Robotics has raised 12 million dollars.` both
  > support a `funding_total` of `12000000`, and `Acme Robotics employs about 120 people.`
  > supports a `headcount_range` of `51-200`.

Referenced tests: `test_evidence.py::test_R1_43_R1_44_R1_133_long_sentence_full_support`, `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_synthetic.py::test_R1_44_R1_133_R1_147_rumoured_funding_is_unknown`, `test_synthetic.py::test_R1_44_R1_155_R1_158_R1_164_mn_is_one_million`, `test_synthetic.py::test_R1_44_R1_149_R1_157_R1_164_invalid_amount_is_unknown`, `test_synthetic.py::test_R1_44_R1_155_R1_164_large_amount_exact`, `test_synthetic.py::test_R1_3_R1_43_R1_44_citation_length_limit`, `test_synthetic.py::test_R1_43_R1_44_R1_86_long_sentence_full_context`

### R1.45
- Section: Evidence and support
- Spec lines: 232-234
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > A research answer carries a claimed value for a field and a citation for the claim. The
  > claim is asserted only when its citation supports it. A field is `unknown` when no evidence
  > supports a value for it, even when a research answer claims one.

Referenced tests: `test_evidence.py::test_R1_41_R1_45_R1_86_cross_company_and_research_evidence`, `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_synthetic.py::test_R1_41_R1_45_R1_86_unsearchable_page_only_claimed_field`, `test_synthetic.py::test_R1_40_R1_45_R1_86_R1_126_research_zero_is_known_and_importable`

### R1.46
- Section: Evidence and support
- Spec lines: 236-237
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > When the evidence supports more than one value for a field, the field holds one of them and
  > cites only excerpts that support that value.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.47
- Section: Pages
- Spec lines: 241-249
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > Every page has a URL, a title and a text. A text may begin with **header lines**, each of
  > the form `Name: value`, where the name is a capitalised word or several joined by `-`. The
  > header ends at the first empty line; everything after it is the page's **prose**. A text
  > whose first line is not a header line has no header and is all prose.
  >
  > The header line `Facts:` carries a JSON object on the same line. Its keys are field names
  > from the table above, and its values are what the page states for those fields, in any
  > format. It is informative only: citations come from the prose, and whether an excerpt
  > supports a value is decided by Appendix A alone. The service may ignore other header lines.

Referenced tests: `test_evidence.py::test_R1_47_R1_131_sentence_boundaries_and_header`, `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.48
- Section: Fixture format
- Spec lines: 251-268
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > ### Fixture format
  >
  > ```json
  > {
  >   "now": "2026-03-01T09:00:00+00:00",
  >   "users": [
  >     { "id": "u_ada", "email": "ada@example.com", "password": "correct horse",
  >       "display_name": "Ada" },
  >     { "id": "u_bob", "email": "bob@example.com", "password": "correct horse",
  >       "display_name": "Bob" }
  >   ]
  > }
  > ```
  >
  > - `now` is required and sets the clock (§3.4).
  > - Seeded users must be able to log in with the given password immediately.
  > - A fixture with two users sharing an email is a reset error: 422 `validation_failed`,
  >   changing nothing.

Referenced tests: `test_api.py::test_R1_23_R1_48_R1_63_R1_65_R1_66_R1_69_auth_reset`, `test_foundation.py::test_R1_23_R1_48_R1_63_R1_66_seed_and_reset`, `test_foundation.py::test_R1_23_R1_34_R1_48_R1_66_fixture_values_and_import`, `test_foundation.py::test_R1_23_R1_33_R1_48_fixture_validation_atomic`, `test_foundation.py::test_R1_23_R1_48_missing_fixture_field`, `test_foundation.py::test_R1_23_R1_48_fixture_duplicate_ids_atomic`, `test_foundation.py::test_R1_17_R1_23_R1_48_500_seeded_users`

### R1.49
- Section: 5. Errors
- Spec lines: 272-272
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Every 4xx and 5xx response carries this body:

Referenced tests: `test_api.py::test_R1_15_R1_21_R1_22_R1_49_health`, `test_api.py::test_R1_49_R1_50_R1_51_R1_56_R1_57_R1_64_R1_65_signup_validation`, `test_api.py::test_R1_49_R1_51_R1_56_malformed_body_types`, `test_foundation.py::test_R1_49_R1_50_R1_54_error_envelope_unknown_route`, `test_foundation.py::test_R1_31_R1_49_RL28_oversize_body_has_413_envelope`, `test_foundation.py::test_R1_31_R1_49_RL49_malformed_chunk_framing_is_atomic`, `test_foundation.py::test_R1_31_R1_49_RL42_unframed_request_has_no_body_and_service_stays_healthy`, `test_foundation.py::test_R1_31_R1_49_RL30_keepalive_recovers_after_oversize`

### R1.50
- Section: 5. Errors
- Spec lines: 278-279
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Use the specified HTTP status and `code`. The human-readable `message` may use any wording.
  > Endpoint-specific errors are listed with each endpoint.

Referenced tests: `test_api.py::test_R1_49_R1_50_R1_51_R1_56_R1_57_R1_64_R1_65_signup_validation`, `test_foundation.py::test_R1_49_R1_50_R1_54_error_envelope_unknown_route`

### R1.51
- Section: 5. Errors
- Spec lines: 283-283
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > | 400 | `malformed_request` | Unparseable body, or a field of the wrong JSON type |

Referenced tests: `test_api.py::test_R1_49_R1_50_R1_51_R1_56_R1_57_R1_64_R1_65_signup_validation`, `test_api.py::test_R1_49_R1_51_R1_56_malformed_body_types`, `test_api.py::test_R1_35_R1_51_R1_57_R1_94_invalid_domains`

### R1.52
- Section: 5. Errors
- Spec lines: 284-284
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | 400 | `missing_idempotency_key` | Required `Idempotency-Key` header absent or empty |

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`

### R1.53
- Section: 5. Errors
- Spec lines: 285-285
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > | 401 | `unauthenticated` | Missing, malformed or unknown bearer token |

Referenced tests: `test_api.py::test_R1_53_R1_67_R1_68_auth_precedes_key`, `test_api.py::test_R1_53_R1_67_missing_auth_all_routes`

### R1.54
- Section: 5. Errors
- Spec lines: 286-286
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > | 404 | `not_found` | No such resource, or not visible to this caller |

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`, `test_foundation.py::test_R1_49_R1_50_R1_54_error_envelope_unknown_route`

### R1.55
- Section: 5. Errors
- Spec lines: 287-287
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | 409 | `idempotency_key_reuse` | Key already used by this caller with a different request body |

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`, `test_api.py::test_R1_16_R1_55_R1_62_R1_77_R1_80_R1_129_concurrent_conflicting`

### R1.56
- Section: 5. Errors
- Spec lines: 288-288
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > | 422 | `validation_failed` | A required field or query parameter is missing, or a stated rule is violated with no more specific code |

Referenced tests: `test_api.py::test_R1_49_R1_50_R1_51_R1_56_R1_57_R1_64_R1_65_signup_validation`, `test_api.py::test_R1_49_R1_51_R1_56_malformed_body_types`

### R1.57
- Section: 5. Errors
- Spec lines: 290-291
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > A field of the correct JSON type with an invalid format or out-of-range value gives
  > 422 `validation_failed`, unless an endpoint specifies a different error. In addition:

Referenced tests: `test_api.py::test_R1_49_R1_50_R1_51_R1_56_R1_57_R1_64_R1_65_signup_validation`, `test_api.py::test_R1_35_R1_51_R1_57_R1_94_invalid_domains`

### R1.58
- Section: 5. Errors
- Spec lines: 293-295
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > - An integer-valued **query parameter** is written as plain decimal digits: `1e9`, `4.0` and `+4`
  >   are 422 `validation_failed` whatever their numeric value.
  > - Reserve 400 `malformed_request` for a body that does not parse or a field of the wrong type.

Referenced tests: `test_api.py::test_R1_58_R1_61_R1_109_pagination_invalid`, `test_api.py::test_R1_58_R1_61_R1_62_extreme_decimal_offset`, `test_api.py::test_R1_58_R1_61_R1_62_extreme_decimal_limit`

### R1.59
- Section: 5. Errors
- Spec lines: 297-297
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Shared ranges, enforced on every endpoint that takes them:

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`, `test_api.py::test_R1_59_R1_60_R1_78_key_boundaries_and_failed_refresh_reuse`

### R1.60
- Section: 5. Errors
- Spec lines: 301-301
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | `Idempotency-Key` | 1 to 255 characters | 422 `validation_failed` |

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`, `test_api.py::test_R1_59_R1_60_R1_78_key_boundaries_and_failed_refresh_reuse`

### R1.61
- Section: 5. Errors
- Spec lines: 302-303
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | `limit` | integer 1 to 200 | 422 `validation_failed` |
  > | `offset` | integer 0 or more | 422 `validation_failed` |

Referenced tests: `test_api.py::test_R1_58_R1_61_R1_109_pagination_invalid`, `test_api.py::test_R1_58_R1_61_R1_62_extreme_decimal_offset`, `test_api.py::test_R1_58_R1_61_R1_62_extreme_decimal_limit`

### R1.62
- Section: 5. Errors
- Spec lines: 305-306
- Package: all / prover
- Status: open
- Text:

  > Requests must not produce 5xx responses, including under concurrent load and when a
  > provider endpoint answers with an error.

Referenced tests: `test_api.py::test_R1_58_R1_61_R1_62_extreme_decimal_offset`, `test_api.py::test_R1_58_R1_61_R1_62_extreme_decimal_limit`, `test_api.py::test_R1_2_R1_16_R1_17_R1_62_R1_80_R1_93_R1_129_concurrent_identical`, `test_api.py::test_R1_16_R1_55_R1_62_R1_77_R1_80_R1_129_concurrent_conflicting`, `test_api.py::test_R1_16_R1_17_R1_62_R1_65_R1_69_R1_129_concurrent_signup`, `test_api.py::test_R1_16_R1_17_R1_62_R1_69_concurrent_logins`, `test_api.py::test_R1_16_R1_62_R1_93_R1_129_concurrent_different_keys`, `test_foundation.py::test_R1_31_R1_62_R1_64_R1_127_surrogate_round_trip`, `test_foundation.py::test_R1_62_R1_107_surrogate_query_does_not_fail`, `test_state_faults.py::test_R1_9_R1_62_R1_85_provider_errors`, `test_state_faults.py::test_R1_9_R1_62_R1_85_nimble_failure`, `test_state_faults.py::test_R1_62_R1_85_R1_87_rate_limits`, `test_synthetic.py::test_R1_42_R1_62_retry_refused_nimble_domain_search`

### R1.63
- Section: 6. Authentication
- Spec lines: 310-311
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Authentication supports signup and login. Email verification, password reset, refresh
  > tokens and role-management endpoints are out of scope.

Referenced tests: `test_api.py::test_R1_23_R1_48_R1_63_R1_65_R1_66_R1_69_auth_reset`, `test_foundation.py::test_R1_23_R1_48_R1_63_R1_66_seed_and_reset`

### R1.64
- Section: 6. Authentication
- Spec lines: 313-325
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > ```http
  > POST /auth/signup
  > { "email": "a@example.com", "password": "correct horse", "display_name": "Ada" }
  >
  > ->  201  { "user_id": "u_1", "display_name": "Ada", "token": "..." }
  > ```
  >
  > ```http
  > POST /auth/login
  > { "email": "a@example.com", "password": "correct horse" }
  >
  > ->  200  { "user_id": "u_1", "display_name": "Ada", "token": "..." }
  > ```

Referenced tests: `test_api.py::test_R1_49_R1_50_R1_51_R1_56_R1_57_R1_64_R1_65_signup_validation`, `test_api.py::test_R1_31_R1_33_R1_64_signup_extra_fields`, `test_foundation.py::test_R1_31_R1_62_R1_64_R1_127_surrogate_round_trip`

### R1.65
- Section: 6. Authentication
- Spec lines: 329-333
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > | Email already registered | 409 `email_taken` |
  > | Password shorter than 8 characters | 422 `validation_failed` |
  > | `email` not of the form `local@domain` | 422 `validation_failed` |
  > | `display_name` empty or longer than 100 characters | 422 `validation_failed` |
  > | Wrong password or unknown email on login | 401 `unauthenticated` |

Referenced tests: `test_api.py::test_R1_23_R1_48_R1_63_R1_65_R1_66_R1_69_auth_reset`, `test_api.py::test_R1_49_R1_50_R1_51_R1_56_R1_57_R1_64_R1_65_signup_validation`, `test_api.py::test_R1_16_R1_17_R1_62_R1_65_R1_69_R1_129_concurrent_signup`

### R1.66
- Section: 6. Authentication
- Spec lines: 335-335
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > For a user seeded by the fixture (§3.3), `user_id` is that user's `id` in the fixture.

Referenced tests: `test_api.py::test_R1_23_R1_48_R1_63_R1_65_R1_66_R1_69_auth_reset`, `test_foundation.py::test_R1_23_R1_48_R1_63_R1_66_seed_and_reset`, `test_foundation.py::test_R1_23_R1_34_R1_48_R1_66_fixture_values_and_import`

### R1.67
- Section: 6. Authentication
- Spec lines: 337-339
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Every other endpoint requires a bearer token, except `/health`, the `/_test/*` endpoints and
  > the two above. A request to such an endpoint that lacks a valid token is 401
  > `unauthenticated`, even when it also lacks a required `Idempotency-Key`.

Referenced tests: `test_api.py::test_R1_53_R1_67_R1_68_auth_precedes_key`, `test_api.py::test_R1_53_R1_67_missing_auth_all_routes`, `test_state_faults.py::test_R1_23_R1_67_R1_93_R1_129_reset_races_authenticated_opens`, `test_state_faults.py::test_R1_23_R1_67_R1_129_reset_races_authenticated_reads`

### R1.68
- Section: 6. Authentication
- Spec lines: 341-343
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > ```http
  > Authorization: Bearer <token>
  > ```

Referenced tests: `test_api.py::test_R1_53_R1_67_R1_68_auth_precedes_key`

### R1.69
- Section: 6. Authentication
- Spec lines: 345-345
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Tokens do not expire. An account may have multiple valid tokens and concurrent sessions.

Referenced tests: `test_api.py::test_R1_23_R1_48_R1_63_R1_65_R1_66_R1_69_auth_reset`, `test_api.py::test_R1_16_R1_17_R1_62_R1_65_R1_69_R1_129_concurrent_signup`, `test_api.py::test_R1_16_R1_17_R1_62_R1_69_concurrent_logins`

### R1.70
- Section: 6. Authentication
- Spec lines: 347-348
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Passwords must be stored using a password-hashing function such as bcrypt, scrypt or
  > Argon2, or an equivalent. Plaintext password storage is not permitted.

Referenced tests: `test_foundation.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_foundation_snapshot`, `test_foundation.py::test_R1_17_R1_70_R1_126_RL27_import_rejects_other_scrypt_parameters`, `test_foundation.py::test_R1_70_R1_126_R1_127_invalid_snapshot_entries_are_atomic`, `test_state_faults.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_export_import_roundtrip`

### R1.71
- Section: 7. Idempotency
- Spec lines: 352-354
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > Two write paths require an idempotency key (§8): **`POST /dossiers`** and
  > **`POST /dossiers/{domain}/refresh`**. Everything below applies to each of them
  > independently.

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`

### R1.72
- Section: 7. Idempotency
- Spec lines: 360-361
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > The key is scoped to **the authenticated user**. Two different users may use the same key string
  > with no interaction between them.

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`

### R1.73
- Section: 7. Idempotency
- Spec lines: 363-366
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > A replay means the same user sending the **same method, the same path and the same body**. The
  > same key with the same body on a different path is a different request, not a replay, and must
  > succeed normally. `Acme-Robotics.test` and `acme-robotics.test` in a path or body are different
  > requests for this rule, though they name the same dossier.

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`

### R1.74
- Section: 7. Idempotency
- Spec lines: 370-370
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | Header absent or empty | 400 `missing_idempotency_key` |

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`

### R1.75
- Section: 7. Idempotency
- Spec lines: 371-371
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | First use of the key | The normal response (§8) |

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`

### R1.76
- Section: 7. Idempotency
- Spec lines: 372-372
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | Replay: same key, same body | **200**, body identical to the original response as a JSON value |

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`

### R1.77
- Section: 7. Idempotency
- Spec lines: 373-373
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | Same key, different body | 409 `idempotency_key_reuse` |

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`, `test_api.py::test_R1_16_R1_55_R1_62_R1_77_R1_80_R1_129_concurrent_conflicting`

### R1.78
- Section: 7. Idempotency
- Spec lines: 374-374
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | Key reused after the original request failed with 4xx | Treated as a first use |

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`, `test_api.py::test_R1_59_R1_60_R1_78_key_boundaries_and_failed_refresh_reuse`

### R1.79
- Section: 7. Idempotency
- Spec lines: 376-380
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > "Same body" means the same JSON value after parsing — key order and whitespace do not matter.
  > Unknown fields are ignored (§3.5) and play no part in this comparison: a body that differs
  > from the first only in unknown fields is the same body, so the request is a replay.
  > `POST /dossiers/{domain}/refresh` takes no body; any body sent to it is ignored and plays no
  > part in deciding a replay.

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`

### R1.80
- Section: 7. Idempotency
- Spec lines: 382-383
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > For concurrent identical requests with an unused key, exactly one returns the normal
  > response. The others return 200 with the same body. The operation takes effect only once.

Referenced tests: `test_api.py::test_R1_2_R1_16_R1_17_R1_62_R1_80_R1_93_R1_129_concurrent_identical`, `test_api.py::test_R1_16_R1_55_R1_62_R1_77_R1_80_R1_129_concurrent_conflicting`

### R1.81
- Section: 7. Idempotency
- Spec lines: 385-386
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > A successful replay returns the original response, even after the dossier has changed. It
  > starts no build and makes no provider call.

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`, `test_api.py::test_R1_81_R1_89_R1_101_R1_102_R1_103_refresh_and_replay`

### R1.82
- Section: 7. Idempotency
- Spec lines: 388-390
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > After the body has parsed as a JSON object and the caller is authenticated, an already
  > claimed key is resolved before field validation. Thus changing a successful request to an
  > invalid body with the same key still returns `409 idempotency_key_reuse`.

Referenced tests: `test_api.py::test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency`

### R1.83
- Section: Builds
- Spec lines: 396-399
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > A **build** researches one dossier: it calls the providers, decides each field, and replaces
  > the dossier's fields with the result when it completes. A dossier's first build starts with
  > `POST /dossiers`, and every later one with `POST /dossiers/{domain}/refresh`. A build's
  > **time** is the clock's time when the request that started it was received.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.84
- Section: Builds
- Spec lines: 401-401
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - A dossier has at most one build running at a time.

Referenced tests: `test_state_faults.py::test_R1_84_R1_102_concurrent_refresh_one_build`, `test_state_faults.py::test_R1_23_R1_84_R1_128_reset_during_build`

### R1.85
- Section: Builds
- Spec lines: 402-403
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - A build ends in `ready` when it completed, or `failed` when none of its provider calls
  >   succeeded. A failed build leaves the fields as they were.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_foundation.py::test_R1_25_R1_27_R1_85_R1_96_RL27_boundary_offset_build_completes`, `test_state_faults.py::test_R1_9_R1_62_R1_85_provider_errors`, `test_state_faults.py::test_R1_9_R1_62_R1_85_nimble_failure`, `test_state_faults.py::test_R1_62_R1_85_R1_87_rate_limits`, `test_state_faults.py::test_R1_85_failed_refresh_preserves_ready_fields`, `test_state_faults.py::test_R1_85_R1_125_R1_126_R1_128_snapshot_failed_and_running_refresh`

### R1.86
- Section: Builds
- Spec lines: 404-405
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > - When a build completes `ready`, each field is `known` exactly when the evidence (§4)
  >   supports a value for it.

Referenced tests: `test_evidence.py::test_R1_41_R1_45_R1_86_cross_company_and_research_evidence`, `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_synthetic.py::test_R1_3_R1_41_R1_43_R1_86_dual_provider_texts_at_one_url`, `test_synthetic.py::test_R1_41_R1_43_R1_86_RL25_evidence_uses_mock_served_variant`, `test_synthetic.py::test_R1_41_R1_45_R1_86_unsearchable_page_only_claimed_field`, `test_synthetic.py::test_R1_40_R1_45_R1_86_R1_126_research_zero_is_known_and_importable`, `test_synthetic.py::test_R1_3_R1_43_R1_86_long_sentence_supporting_prefix`, `test_synthetic.py::test_R1_43_R1_44_R1_86_long_sentence_full_context`

### R1.87
- Section: Builds
- Spec lines: 406-407
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > - A build whose provider calls each answer within one second ends within 10 seconds of the
  >   request that started it.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_state_faults.py::test_R1_62_R1_85_R1_87_rate_limits`, `test_state_faults.py::test_R1_87_delay_under_one_second`

### R1.89
- Section: Builds
- Spec lines: 413-414
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - Reading a dossier, listing dossiers and every other request except `POST /dossiers` and
  >   `POST /dossiers/{domain}/refresh` make no provider call.

Referenced tests: `test_api.py::test_R1_81_R1_89_R1_101_R1_102_R1_103_refresh_and_replay`, `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.90
- Section: `POST /dossiers`
- Spec lines: 418-418
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > **An idempotent write path.** `Idempotency-Key` is required; see §7.

Referenced tests: `test_api.py::test_R1_90_R1_91_R1_104_R1_106_dossier_contract`

### R1.91
- Section: `POST /dossiers`
- Spec lines: 420-431
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > ```http
  > POST /dossiers
  > Authorization: Bearer <token>
  > Idempotency-Key: 2f9c1a...
  >
  > { "domain": "acme-robotics.test" }
  > ```
  >
  > ```json
  > 202
  > { "dossier_id": "d_7", "domain": "acme-robotics.test", "state": "building" }
  > ```

Referenced tests: `test_api.py::test_R1_90_R1_91_R1_104_R1_106_dossier_contract`

### R1.92
- Section: `POST /dossiers`
- Spec lines: 433-435
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > When no dossier exists for the domain, the service creates one, starts its first build and
  > returns 202. When a dossier already exists for the domain, the service starts no build and
  > returns **200** with that dossier's `dossier_id`, `domain` and current `state`.

Referenced tests: `test_api.py::test_R1_31_R1_35_R1_36_R1_92_R1_100_normalisation`

### R1.93
- Section: `POST /dossiers`
- Spec lines: 437-438
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > Concurrent requests for the same domain create one dossier and start one build, whatever
  > their keys.

Referenced tests: `test_api.py::test_R1_2_R1_16_R1_17_R1_62_R1_80_R1_93_R1_129_concurrent_identical`, `test_api.py::test_R1_16_R1_62_R1_93_R1_129_concurrent_different_keys`, `test_state_faults.py::test_R1_23_R1_67_R1_93_R1_129_reset_races_authenticated_opens`

### R1.94
- Section: `POST /dossiers`
- Spec lines: 442-443
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | `domain` missing | 422 `validation_failed` |
  > | `domain` invalid after normalisation (§4) | 422 `validation_failed` |

Referenced tests: `test_api.py::test_R1_35_R1_51_R1_57_R1_94_invalid_domains`

### R1.95
- Section: `GET /dossiers/{domain}`
- Spec lines: 447-463
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > ```json
  > {
  >   "dossier_id": "d_7",
  >   "domain": "acme-robotics.test",
  >   "state": "ready",
  >   "researched_at": "2026-03-01T09:00:00+00:00",
  >   "spent_units": 34,
  >   "fields": {
  >     "legal_name": { "value": "Acme Robotics, Inc.", "status": "known", "citations": [ { "...": "..." } ] },
  >     "hq_city": { "value": "Lisbon", "status": "known", "citations": [ { "...": "..." } ] },
  >     "ceo": { "value": null, "status": "unknown", "citations": [] },
  >     "founded_year": { "value": 2014, "status": "known", "citations": [ { "...": "..." } ] },
  >     "headcount_range": { "value": "51-200", "status": "known", "citations": [ { "...": "..." } ] },
  >     "funding_total": { "value": 12000000, "status": "known", "citations": [ { "...": "..." } ] }
  >   }
  > }
  > ```

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.96
- Section: `GET /dossiers/{domain}`
- Spec lines: 465-466
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - `state` is `building` while a build runs, otherwise the outcome of the latest build,
  >   `ready` or `failed`.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_foundation.py::test_R1_25_R1_27_R1_85_R1_96_RL27_boundary_offset_build_completes`

### R1.97
- Section: `GET /dossiers/{domain}`
- Spec lines: 467-469
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - `fields` always holds all six fields. Before the first build completes `ready`, every
  >   field is `unknown`. While a later build runs, `fields` are those of the last build that
  >   completed `ready`.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_state_faults.py::test_R1_97_R1_128_export_refresh_in_progress`

### R1.98
- Section: `GET /dossiers/{domain}`
- Spec lines: 470-470
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - `researched_at` is the time of the last build that completed `ready`, or null.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.99
- Section: `GET /dossiers/{domain}`
- Spec lines: 471-472
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - `spent_units` is the total cost (§9) of every provider call made for this dossier, by
  >   every build, since it was created.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_state_faults.py::test_R1_99_R1_121_R1_122_tavily_rate_limit_refusal_costs_zero`, `test_synthetic.py::test_R1_99_R1_121_refusals_cost_nothing`, `test_synthetic.py::test_R1_99_R1_117_R1_118_missing_extract_is_charged`

### R1.100
- Section: `GET /dossiers/{domain}`
- Spec lines: 473-473
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - The domain in the path is normalised (§4). No dossier for it is 404 `not_found`.

Referenced tests: `test_api.py::test_R1_31_R1_35_R1_36_R1_92_R1_100_normalisation`

### R1.101
- Section: `POST /dossiers/{domain}/refresh`
- Spec lines: 477-477
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > **An idempotent write path.** `Idempotency-Key` is required; see §7. No body.

Referenced tests: `test_api.py::test_R1_81_R1_89_R1_101_R1_102_R1_103_refresh_and_replay`

### R1.102
- Section: `POST /dossiers/{domain}/refresh`
- Spec lines: 479-481
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > Starts a new build of the dossier and returns 202 with
  > `{ "dossier_id", "domain", "state": "building" }`. A refresh received while a build of the
  > dossier is running starts no second build and returns 202 with the same body.

Referenced tests: `test_api.py::test_R1_81_R1_89_R1_101_R1_102_R1_103_refresh_and_replay`, `test_state_faults.py::test_R1_84_R1_102_concurrent_refresh_one_build`

### R1.103
- Section: `POST /dossiers/{domain}/refresh`
- Spec lines: 483-484
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > A refresh researches again: its build makes provider calls whether or not anything has
  > changed since the last build, and its spending counts in `spent_units`.

Referenced tests: `test_api.py::test_R1_81_R1_89_R1_101_R1_102_R1_103_refresh_and_replay`

### R1.104
- Section: `POST /dossiers/{domain}/refresh`
- Spec lines: 488-488
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > | No dossier for the domain | 404 `not_found` |

Referenced tests: `test_api.py::test_R1_90_R1_91_R1_104_R1_106_dossier_contract`

### R1.105
- Section: `GET /dossiers`
- Spec lines: 492-501
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > ```http
  > GET /dossiers?q=acme&limit=50&offset=0
  > ```
  >
  > ```json
  > { "dossiers": [ { "dossier_id": "d_7", "domain": "acme-robotics.test", "state": "ready",
  >                   "legal_name": "Acme Robotics, Inc.", "researched_at": "2026-03-01T09:00:00+00:00",
  >                   "spent_units": 34 } ],
  >   "has_more": false }
  > ```

Referenced tests: `test_api.py::test_R1_32_R1_34_R1_105_R1_107_R1_108_R1_109_order_and_pagination`

### R1.106
- Section: `GET /dossiers`
- Spec lines: 503-503
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - `legal_name` is the value of the dossier's `legal_name` field, or null.

Referenced tests: `test_api.py::test_R1_90_R1_91_R1_104_R1_106_dossier_contract`

### R1.107
- Section: `GET /dossiers`
- Spec lines: 504-505
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - `q` is optional. When present, only dossiers whose domain or `legal_name` contains `q`,
  >   compared case-insensitively, are listed. An empty `q` lists every dossier.

Referenced tests: `test_api.py::test_R1_32_R1_34_R1_105_R1_107_R1_108_R1_109_order_and_pagination`, `test_foundation.py::test_R1_62_R1_107_surrogate_query_does_not_fail`

### R1.108
- Section: `GET /dossiers`
- Spec lines: 506-506
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - Dossiers are ordered by domain ascending.

Referenced tests: `test_api.py::test_R1_32_R1_34_R1_105_R1_107_R1_108_R1_109_order_and_pagination`

### R1.109
- Section: `GET /dossiers`
- Spec lines: 507-508
- Package: P3 dossier API (builder-a)
- Status: open
- Text:

  > - `limit` defaults to 50, range 1 to 200. `offset` defaults to 0. `has_more` is true when
  >   items exist beyond the last one returned.

Referenced tests: `test_api.py::test_R1_58_R1_61_R1_109_pagination_invalid`, `test_api.py::test_R1_32_R1_34_R1_105_R1_107_R1_108_R1_109_order_and_pagination`

### R1.110
- Section: 9. Providers and cost
- Spec lines: 512-512
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > Each provider call has a cost in **units**:

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.111
- Section: 9. Providers and cost
- Spec lines: 516-516
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Search through `nimble`, depth `lite` (title, URL and snippet) | 1 |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.112
- Section: 9. Providers and cost
- Spec lines: 517-517
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Search through `nimble`, depth `fast` (a truncated page body) | 5 |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.113
- Section: 9. Providers and cost
- Spec lines: 518-518
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Search through `nimble`, depth `deep` (the full page) | 15 |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.114
- Section: 9. Providers and cost
- Spec lines: 519-519
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Search through `tavily`, depth `lite` (title, URL and snippet) | 8 |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.115
- Section: 9. Providers and cost
- Spec lines: 520-520
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Search through `tavily`, depth `fast` (title, URL and a longer snippet) | 16 |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.116
- Section: 9. Providers and cost
- Spec lines: 521-521
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Search through `tavily`, depth `deep` (the full page) | 16 |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.117
- Section: 9. Providers and cost
- Spec lines: 522-522
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Extract through `nimble` | 1 per URL requested, including a URL for which no page is returned |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_synthetic.py::test_R1_99_R1_117_R1_118_missing_extract_is_charged`

### R1.118
- Section: 9. Providers and cost
- Spec lines: 523-523
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Extract through `tavily` | 2 per URL requested, including a URL for which no page is returned |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_synthetic.py::test_R1_99_R1_117_R1_118_missing_extract_is_charged`

### R1.119
- Section: 9. Providers and cost
- Spec lines: 524-524
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > | Research run through `nimble` | 25 when the run is started; checking on or collecting a run costs nothing |

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.120
- Section: 9. Providers and cost
- Spec lines: 526-526
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > A search's depth is WebRouter's `search_depth`.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.121
- Section: 9. Providers and cost
- Spec lines: 528-533
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > A search returns at most 10 results, whatever number it asks for. A call that a provider
  > refuses with an error status costs nothing. A call whose answer does not arrive, because it
  > times out or its connection fails, costs its units as in the table, whether or not the
  > provider received it. An extract that the provider answers with no page
  > for the URL is not refused: it costs its units, as in the table, whatever status says so. An
  > extract through `nimble` does not set `render`.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_state_faults.py::test_R1_99_R1_121_R1_122_tavily_rate_limit_refusal_costs_zero`, `test_synthetic.py::test_R1_99_R1_121_refusals_cost_nothing`

### R1.122
- Section: 9. Providers and cost
- Spec lines: 535-536
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > A build stops making provider calls before its spending would exceed 80 units, and completes
  > with the pages and research claims it has obtained.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`, `test_state_faults.py::test_R1_99_R1_121_R1_122_tavily_rate_limit_refusal_costs_zero`

### R1.123
- Section: 9. Providers and cost
- Spec lines: 538-539
- Package: P4 research engine (builder-b)
- Status: open
- Text:

  > A research request names the company by its domain in its query, and names the fields it
  > asks for by the field names in §4, as the property names of its output schema.

Referenced tests: `test_evidence.py::test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost`

### R1.124
- Section: 10. Export and import
- Spec lines: 543-544
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > The service must support `GET /_test/export` and `POST /_test/import`. Like reset, these
  > are unauthenticated control endpoints.

Referenced tests: `test_foundation.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_foundation_snapshot`, `test_state_faults.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_export_import_roundtrip`

### R1.125
- Section: 10. Export and import
- Spec lines: 545-548
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Exports may contain credentials and session tokens; handle them as private artifacts.
  > Return 200 from export with a JSON object containing `track: "dossier"`,
  > `format_version: 1` and `state` (an implementation-defined JSON object). The state format
  > is opaque to the caller and must be accepted unchanged by import.

Referenced tests: `test_foundation.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_foundation_snapshot`, `test_foundation.py::test_R1_33_R1_125_R1_126_RL20_max_counter_export_after_signup_round_trips`, `test_state_faults.py::test_R1_85_R1_125_R1_126_R1_128_snapshot_failed_and_running_refresh`, `test_state_faults.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_export_import_roundtrip`

### R1.126
- Section: 10. Export and import
- Spec lines: 550-556
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Import takes that entire object and atomically replaces the service's state, returning
  > 204. It must accept an unchanged export produced by this service. No dependency on the
  > source process, files, volume, port or network address is allowed. Import is replacement,
  > not merge; repeating it restores the exported state without duplicating anything. Invalid
  > JSON follows §5; missing fields, wrong track/version or an invalid state give 422
  > `validation_failed` without changing the destination. These control calls have a 10-second
  > timeout. Export is an atomic, read-only snapshot; subsequent source writes do not change it.

Referenced tests: `test_foundation.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_foundation_snapshot`, `test_foundation.py::test_R1_33_R1_125_R1_126_RL20_max_counter_export_after_signup_round_trips`, `test_foundation.py::test_R1_17_R1_70_R1_126_RL27_import_rejects_other_scrypt_parameters`, `test_foundation.py::test_R1_126_missing_export_sections_rejected_atomically`, `test_foundation.py::test_R1_70_R1_126_R1_127_invalid_snapshot_entries_are_atomic`, `test_state_faults.py::test_R1_85_R1_125_R1_126_R1_128_snapshot_failed_and_running_refresh`, `test_state_faults.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_export_import_roundtrip`, `test_state_faults.py::test_R1_126_invalid_import_does_not_replace_state`, `test_synthetic.py::test_R1_40_R1_45_R1_86_R1_126_research_zero_is_known_and_importable`, `test_synthetic.py::test_R1_40_R1_126_R1_127_invalid_dossier_snapshot_is_atomic`, `test_synthetic.py::test_R1_38_R1_40_R1_126_invalid_import_field_values`, `test_synthetic.py::test_R1_40_R1_43_R1_126_invalid_import_citation`

### R1.127
- Section: 10. Export and import
- Spec lines: 558-566
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > Preserve accounts and hashed-password login, existing bearer tokens, dossiers with their
  > ids, states, fields, citations, `researched_at` and `spent_units`, all completed idempotent
  > request bodies and original responses. Identities and timestamps must not be regenerated.
  > Import makes no provider call: imported dossiers are not researched again, and their
  > citations remain citations served to this service. Failed request keys remain reusable.
  > Existing tokens and retries must remain valid after import; replacing the state with a fresh
  > fixture does not satisfy this requirement. Import removes all previous destination data and
  > credentials. Reset clears all state, including imported state. Export and import do not
  > change the clock. State need not survive an abrupt container restart.

Referenced tests: `test_foundation.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_foundation_snapshot`, `test_foundation.py::test_R1_31_R1_62_R1_64_R1_127_surrogate_round_trip`, `test_foundation.py::test_R1_70_R1_126_R1_127_invalid_snapshot_entries_are_atomic`, `test_state_faults.py::test_R1_70_R1_124_R1_125_R1_126_R1_127_export_import_roundtrip`, `test_synthetic.py::test_R1_40_R1_126_R1_127_invalid_dossier_snapshot_is_atomic`

### R1.128
- Section: 10. Export and import
- Spec lines: 568-570
- Package: P1 foundation (builder-a)
- Status: open
- Text:

  > An export taken while a build is running holds the dossier as it was before that build;
  > after import, that dossier is in the state of its last completed build, or `failed` with
  > every field `unknown` when no build had completed.

Referenced tests: `test_state_faults.py::test_R1_85_R1_125_R1_126_R1_128_snapshot_failed_and_running_refresh`, `test_state_faults.py::test_R1_23_R1_84_R1_128_reset_during_build`, `test_state_faults.py::test_R1_128_export_first_build_in_progress`, `test_state_faults.py::test_R1_97_R1_128_export_refresh_in_progress`

### R1.129
- Section: 11. Concurrency
- Spec lines: 574-575
- Package: all / prover
- Status: open
- Text:

  > Concurrent requests must produce the same results as executing them one at a time in some
  > order. The requirements above hold at every read.

Referenced tests: `test_api.py::test_R1_2_R1_16_R1_17_R1_62_R1_80_R1_93_R1_129_concurrent_identical`, `test_api.py::test_R1_16_R1_55_R1_62_R1_77_R1_80_R1_129_concurrent_conflicting`, `test_api.py::test_R1_16_R1_17_R1_62_R1_65_R1_69_R1_129_concurrent_signup`, `test_api.py::test_R1_16_R1_62_R1_93_R1_129_concurrent_different_keys`, `test_state_faults.py::test_R1_23_R1_67_R1_93_R1_129_reset_races_authenticated_opens`, `test_state_faults.py::test_R1_23_R1_67_R1_129_reset_races_authenticated_reads`

### R1.130
- Section: Appendix A. When an excerpt supports a value
- Spec lines: 579-580
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > This appendix is the whole definition of "supports" used in §4. The service decides support
  > by these rules alone.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.131
- Section: A.1 Sentences
- Spec lines: 584-588
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > A page's prose is split into lines at each line break, and each line into sentences. A
  > sentence ends after a `.`, `!` or `?`, together with any `"`, `”`, `’` or `)` directly after
  > it, when whitespace follows. A `.` that ends one of the legal-form suffixes in A.4, written
  > as a whole word, does not end a sentence. Each sentence is taken without its surrounding
  > whitespace; empty sentences are dropped.

Referenced tests: `test_evidence.py::test_R1_47_R1_131_sentence_boundaries_and_header`

### R1.132
- Section: A.1 Sentences
- Spec lines: 590-591
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > An excerpt is a **single sentence** when, with every run of whitespace written as one space,
  > this rule splits it into exactly one sentence.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.133
- Section: A.2 The rule
- Spec lines: 595-604
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > An excerpt supports the value V for the field F of a company exactly when all of these hold:
  >
  > 1. It is a single sentence (A.1).
  > 2. It names the company: it contains the company's normalised domain, or the company's
  >    name. The company's name is the first label of its domain with each `-` read as a space:
  >    `acme-robotics.test` is named by `Acme Robotics`.
  > 3. It contains a statement phrase for F (A.3).
  > 4. It contains none of the negating phrases (A.3).
  > 5. It contains at least one value in F's format (A.4), and every value in F's format that it
  >    contains normalises to V (A.5).

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`, `test_evidence.py::test_R1_43_R1_44_R1_133_long_sentence_full_support`, `test_synthetic.py::test_R1_44_R1_133_R1_147_rumoured_funding_is_unknown`

### R1.134
- Section: A.2 The rule
- Spec lines: 606-608
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > The company's name, its domain and every phrase are matched without regard to case and as
  > whole words: the characters directly before and after the match are not letters or digits.
  > Phrases with a space match one space.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.135
- Section: A.2 The rule
- Spec lines: 614-614
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `Dana Ruiz has led Acme Robotics as chief executive since 2021.` | `ceo` `Dana Ruiz` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.136
- Section: A.2 The rule
- Spec lines: 615-615
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `Acme Robotics CEO: Sam Ortiz.` | `ceo` `Sam Ortiz` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.137
- Section: A.2 The rule
- Spec lines: 616-616
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `Acme Robotics was founded in 2014.` | `founded_year` `2014` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.138
- Section: A.2 The rule
- Spec lines: 617-617
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `Acme Robotics employs about 120 people.` | `headcount_range` `51-200` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.139
- Section: A.2 The rule
- Spec lines: 618-618
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `Acme Robotics is reportedly in talks to raise $40M.` | nothing: a negating phrase |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.140
- Section: A.2 The rule
- Spec lines: 619-619
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `Acme Robotics opened a sales office in Porto.` | nothing: no statement phrase for `hq_city` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.141
- Section: A.3 Phrases
- Spec lines: 625-625
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `legal_name` | `legal name`, `registered name`, `registered as`, `registered company`, `legal entity`, `name of record` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.142
- Section: A.3 Phrases
- Spec lines: 626-626
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `hq_city` | `headquartered in`, `headquarters in`, `head office in`, `based in`, `registered office in`, `registered seat in` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.143
- Section: A.3 Phrases
- Spec lines: 627-627
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `ceo` | `chief executive officer`, `chief executive`, `CEO` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.144
- Section: A.3 Phrases
- Spec lines: 628-628
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `founded_year` | `founded`, `founding`, `established`, `incorporated` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.145
- Section: A.3 Phrases
- Spec lines: 629-629
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `headcount_range` | `employs`, `employees`, `staff`, `people`, `headcount`, `workforce` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.146
- Section: A.3 Phrases
- Spec lines: 630-630
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `funding_total` | `raised`, `funding`, `invested`, `investment` |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.147
- Section: A.3 Phrases
- Spec lines: 632-634
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > The negating phrases are: `in talks to`, `plans to`, `planning to`, `wants to`,
  > `expects to`, `hopes to`, `aims to`, `seeking`, `could`, `would`, `might`, `reportedly`,
  > `rumoured`, `former`, `formerly`, `will become`, `not`.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`, `test_synthetic.py::test_R1_44_R1_133_R1_147_rumoured_funding_is_unknown`

### R1.148
- Section: A.4 Value formats
- Spec lines: 638-641
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > A **capitalised word** is an uppercase letter followed by one or more lowercase letters,
  > with no letter or digit directly before or after it. The letters may be of any alphabet:
  > `Zürich` and `Müller` are capitalised words. An **uppercase word** is two or more uppercase
  > letters, with no letter or digit directly before or after it: `AI`, `USA`.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.149
- Section: A.4 Value formats
- Spec lines: 643-645
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > A **number** is written in digits, optionally with a `,` before each group of three digits
  > and a decimal part after a `.`: `120`, `1,200`, `12.5`, `12,000,000`. Digits directly next to
  > a letter, or joined to other digits by `,` or `.` in any other way, are not a number.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`, `test_synthetic.py::test_R1_44_R1_149_R1_157_R1_164_invalid_amount_is_unknown`

### R1.150
- Section: A.4 Value formats
- Spec lines: 649-649
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `legal_name` | The company's name or its domain (matched as in A.2), then zero or more capitalised or uppercase words each after one space, then an optional `,`, one space, and a legal-form suffix with no letter or digit directly after it. Where several such texts start at the same place, the shortest counts |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.151
- Section: A.4 Value formats
- Spec lines: 650-650
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `hq_city` | A place name directly after a statement phrase for `hq_city` and one space: the longest run of capitalised words joined by single spaces or by `-` that starts there, not part of a longer such run |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.152
- Section: A.4 Value formats
- Spec lines: 651-651
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `ceo` | A person's name: a run of two or three capitalised words joined by single spaces that is not part of a longer such run. Occurrences of the company's name and of the statement phrases for `ceo` are first taken out of the sentence and separate the words around them |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.153
- Section: A.4 Value formats
- Spec lines: 652-652
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `founded_year` | A number of exactly four digits, from 1800 to 2099, that is not part of an amount |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.154
- Section: A.4 Value formats
- Spec lines: 653-653
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `headcount_range` | A number with no decimal part, 1 or more, that is not part of an amount. Words before it, such as `about` or `roughly`, do not change it. A stated range such as `51-200 employees` holds two numbers |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.155
- Section: A.4 Value formats
- Spec lines: 654-654
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `funding_total` | An amount (below) |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`, `test_synthetic.py::test_R1_44_R1_155_R1_158_R1_164_mn_is_one_million`, `test_synthetic.py::test_R1_44_R1_155_R1_164_large_amount_exact`

### R1.156
- Section: A.4 Value formats
- Spec lines: 656-659
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > The legal-form suffixes, matched exactly as written here: `Inc.`, `Corp.`, `LLC`, `LLP`,
  > `L.P.`, `Ltd`, `Limited`, `Pty Ltd`, `plc`, `PLC`, `GmbH`, `AG`, `KG`, `SE`, `AS`, `A/S`,
  > `ASA`, `AB`, `Oy`, `Oyj`, `B.V.`, `N.V.`, `S.A.`, `S.A.S.`, `S.L.`, `S.r.l.`, `S.p.A.`,
  > `s.r.o.`, `a.s.`, `K.K.`.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.157
- Section: A.4 Value formats
- Spec lines: 661-662
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > An **amount** is written in one of these forms, matched without regard to case, with no
  > letter or digit directly before it or after it:

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`, `test_synthetic.py::test_R1_44_R1_149_R1_157_R1_164_invalid_amount_is_unknown`

### R1.158
- Section: A.4 Value formats
- Spec lines: 664-667
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > - `$`, `US$` or `USD`, an optional space, a number, and optionally a scale: `k`, `m`, `mn` or
  >   `bn` directly after the number, or one space and `thousand`, `million` or `billion`.
  >   Examples: `$12M`, `$12.5 million`, `US$12 million`, `USD 12 million`, `$12m`,
  >   `$12,000,000`.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`, `test_synthetic.py::test_R1_44_R1_155_R1_158_R1_164_mn_is_one_million`

### R1.159
- Section: A.4 Value formats
- Spec lines: 668-669
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > - A number, optionally one space and `thousand`, `million` or `billion`, then one space and
  >   `dollars` or `US dollars`. Examples: `12 million dollars`, `12,000,000 US dollars`.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.160
- Section: A.4 Value formats
- Spec lines: 671-671
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > Amounts in other currencies are not amounts.

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.161
- Section: A.5 Normalisation
- Spec lines: 677-677
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `legal_name`, `hq_city`, `ceo` | The text as the excerpt writes it |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.162
- Section: A.5 Normalisation
- Spec lines: 678-678
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `founded_year` | The number as an integer |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.163
- Section: A.5 Normalisation
- Spec lines: 679-679
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `headcount_range` | The range of §4 that contains the number |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`

### R1.164
- Section: A.5 Normalisation
- Spec lines: 680-680
- Package: P2 support rules (builder-b)
- Status: open
- Text:

  > | `funding_total` | The number times the scale (`k` and `thousand` 1,000; `m`, `mn` and `million` 1,000,000; `bn` and `billion` 1,000,000,000) in US dollars. An amount that does not come to a whole number of dollars is not a value |

Referenced tests: `test_evidence.py::test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples`, `test_synthetic.py::test_R1_44_R1_155_R1_158_R1_164_mn_is_one_million`, `test_synthetic.py::test_R1_44_R1_149_R1_157_R1_164_invalid_amount_is_unknown`, `test_synthetic.py::test_R1_44_R1_155_R1_164_large_amount_exact`
