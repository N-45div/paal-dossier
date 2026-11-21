# R2R trace: ledger ids to code and tests

Each line: id, the code that implements it, and the test that exercises it (or `no test`).
Paths are under `stage-2/`. Unit tests are in `tests/unit/`, acceptance tests in `tests/acceptance/`.

| id | code | test |
|---|---|---|
| R2.8 | `app/pages.py` `page_meta` (reads the `Kind` and `Published` header lines) | `tests/unit/test_pages.py` |
| R2.9 | `app/pages.py` `_kind` (declared kind taken exactly) | `tests/unit/test_pages.py::test_declared_kind_is_taken_exactly` |
| R2.10 | `app/pages.py` `_published` | `tests/unit/test_pages.py::test_rfc3339_with_offset_is_kept_as_its_instant` |
| R2.11 | `app/pages.py` `_kind` host fallback | `tests/unit/test_pages.py::test_no_kind_line_uses_the_host_with_www_and_trailing_dot_normalised` |
| R2.12 | `app/pages.py` `_published` returns None | `tests/unit/test_pages.py::test_published_without_offset_or_invalid_has_no_time` |
| R2.13 | `app/gateway.py` `extract` (served prose from extract, header split off by `app/support.py` `split_header`) | no test (indirect: `tests/acceptance/test_dossier_build.py::test_six_fields_shape_citations_and_support`) |
| R2.14 | no control activation is ever made (plain extract only) | no test |
| R2.15 | corpus property; nothing to implement | no test |
| R2.16 | `app/evidence.py` `collect_candidates` uses `extract_supports` on served prose; excerpt is a sentence of that prose | `tests/acceptance/test_dossier_build.py::test_six_fields_shape_citations_and_support` |
| R2.17 | `app/evidence.py` `PROVIDER = "nimble"` (the provider that served the text) | no test that checks `provider` on candidates directly |
| R2.18 | `render` extract not used (Rul-S2-4) | optional, not implemented |
| R2.19 | `provider_options={"render": True}` not passed | optional, not implemented |
| R2.20 | `render: True` on WebRouter extract not passed | optional, not implemented (Rul-S2-4: render only if a ledger requirement fails without it; none did) |
| R2.21 | `kernel` / `browserbase` not used | optional, not implemented |
| R2.22 | `kernel` `open_browser` not used | optional, not implemented |
| R2.23 | `browserbase` `open_browser` / `browse` not used | optional, not implemented |
| R2.24 | service uses only Nimble plain extract for page text | covered by R2.13 behaviour; no test of the render-only option |
| R2.25 | `KERNEL_*` / `BROWSERBASE_*` env vars not read | optional, not implemented |
| R2.26 | `KERNEL_API_KEY` not read | optional, not implemented |
| R2.27 | `KERNEL_BASE_URL` not read | optional, not implemented |
| R2.28 | `BROWSERBASE_API_KEY` not read | optional, not implemented |
| R2.29 | `BROWSERBASE_BASE_URL` not read | optional, not implemented |
| R2.30 | WebRouter reads keys from env; we do not pass them | optional, not implemented |
| R2.31 | `provider_config` for kernel/browserbase not set | optional, not implemented |
| R2.32 | `provider_config={"kernel": ..., "browserbase": ...}` not set | optional, not implemented |
| R2.33 | cost table for optional vendors not applicable | optional, not implemented |
| R2.34 | render extract cost (3 units) not applicable | optional, not implemented |
| R2.35 | kernel session cost not applicable | optional, not implemented |
| R2.36 | browserbase session cost not applicable | optional, not implemented |
| R2.37 | per-page session cost not applicable | optional, not implemented |
| R2.38 | browse run cost not applicable | optional, not implemented |
| R2.39 | failed open/load/release cost nothing (not applicable: no sessions) | optional, not implemented |
| R2.40 | max 4 sessions per provider (not applicable: no sessions) | optional, not implemented |
| R2.41 | 60 s idle session close (not applicable: no sessions) | optional, not implemented |
| R2.42 | `app/gateway.py` `_rate_limited`, `_charged` retry loop | `tests/unit/test_build_spend.py::test_three_429s_are_retried_and_the_build_succeeds`; `tests/acceptance/test_dossier_build.py::test_rate_limited_nimble_still_no_5xx_and_budget_holds` |
| R2.43 | `app/gateway.py` `_attempt`: a refused (429) call releases its reservation | `tests/unit/test_build_spend.py::test_four_429s_give_up_on_that_call_without_spend` |
| R2.44 | `app/gateway.py` `RATE_LIMIT_WAIT_S = 1.05` before any retry of the same call | `tests/unit/test_build_spend.py::test_rate_limit_waits_at_least_one_point_oh_five_seconds` |
| R2.45 | "no call answered 429 more than three times in a row" is a mock property; the service caps its own attempts at 4 (`RATE_LIMIT_ATTEMPTS`) | no test of the mock's guarantee |
| R2.46 | `app/gateway.py` retry waits are not counted by the build deadline logic (waits happen inside `_charged`, not in the 10 s target path) | `tests/acceptance/test_dossier_build.py::test_throttled_research_run_still_ends_well_formed` (indirect; no direct timing assertion for the 10 s bound) |
| R2.48 | `app/evidence.py` `collect_candidates`: one candidate per (field, url, value), first sentence in reading order (Rul-S2-8) | `tests/unit/test_candidates.py::test_one_candidate_per_value_per_page_rul_s2_8`; `tests/acceptance/test_stage2_selection.py::test_every_field_has_candidates_list_and_consistent_selection` |
| R2.49 | `app/research.py` `_gather` phase 1 extracts research-cited URLs not yet gathered | no direct test (indirect: `tests/acceptance/test_stage2_selection.py::test_own_page_beats_newer_news_and_aggregator_and_field_is_contested`) |
| R2.50 | `app/evidence.py` collects candidates only from pages; research claims are never candidates | no test |
| R2.51 | `app/evidence.py` `PROVIDER = "nimble"` (any provider that served the text is allowed) | no test |
| R2.53 | `app/candidates.py` `Candidate` shape (value, url, excerpt, provider, kind, published_at); API candidates in `app/dossiers.py` | `tests/acceptance/test_stage2_selection.py::test_every_field_has_candidates_list_and_consistent_selection` |
| R2.54 | `app/evidence.py` candidate url/excerpt/provider from the served page and the sentence | `tests/acceptance/test_dossier_build.py::test_six_fields_shape_citations_and_support` (indirect) |
| R2.56 | `app/builds.py` stamps `retrieved_at` with the build time (R2S-owned, R2R-listed) | `tests/acceptance/test_stage2_selection.py::test_retrieved_at_is_the_build_time_of_the_last_ready_build` |

## Summary

- Implemented and tested: R2.8–R2.12, R2.16, R2.42–R2.44, R2.46, R2.48, R2.53, R2.56.
- Implemented but with no direct test: R2.13, R2.14, R2.15, R2.17, R2.24, R2.45, R2.49, R2.50, R2.51, R2.54.
- Optional, not implemented (Rul-S2-4 and the spec's "not required"): R2.18–R2.41.
  The render flag and the kernel and browserbase vendors are not used.
- Ids with no test that should get one: R2.17, R2.49, R2.50, R2.51 (candidate provider, research-cited pages, claims never candidates).
- Ids where the text is a mock property or a rule not implemented by the service: R2.14, R2.15, R2.45.
