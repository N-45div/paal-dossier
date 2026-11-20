# Stage 2 acceptance claims and ledger text

Source: lead ledger revision `8ec8b4103b9e420c78fa1b9b9a749d0282adbd38`. A named test identifies an exercised clause, not proof of every subclause. Screenshots require visual review. Optional vendor configuration (R2.20–R2.21) is conditional on vendor use; provider session cap and expiration (R2.29) are directly exercised against the mock. R2.107 does not prohibit background synchronization.

IDs without an individually named test: none.

### R2.1
- Section: (preamble)
- Package: P6
- Status: open
- Text:

  > The stage-1 requirements continue to apply, with the additions below. Numbered section
  > references such as §4 and §7 refer to `stage-1.md`.

Referenced tests: `test_candidates.py::test_R2_1_R2_3_stage1_auth_and_idempotency_remain`

### R2.2
- Section: (preamble)
- Package: P6
- Status: open
- Text:

  > Sources disagree. A dossier now keeps every value its evidence supports, as candidates, and
  > selects one per field by a fixed rule. Researchers read dossiers, their evidence and the
  > fields in dispute in a browser.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.3
- Section: (preamble)
- Package: P6
- Status: open
- Text:

  > The following applies to all operations, in addition to the stage-1 list:

Referenced tests: `test_candidates.py::test_R2_1_R2_3_stage1_auth_and_idempotency_remain`

### R2.4
- Section: (preamble)
- Package: P6
- Status: open
- Text:

  > 3. A field's selected value is the one the selection rule below picks from the field's
  >    candidates; the same candidates always yield the same value.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.5
- Section: Page kind and publication time
- Package: P5
- Status: open
- Text:

  > Two header lines (§4, Pages) now carry requirements:

Referenced tests: `test_candidates.py::test_R2_5_R2_6_R2_7_R2_8_R2_9_R2_31_R2_34_R2_35_rendered_text_and_metadata`, `test_harness.py::test_R2_5_R2_6_R2_7_R2_8_RL66_controlled_provider_serves_metadata_variants`

### R2.6
- Section: Page kind and publication time
- Package: P5
- Status: open
- Text:

  > | `Kind: own`, `Kind: filing`, `Kind: news`, `Kind: aggregator` | The page's **kind**: the company's own site, a filing registry, a news report, or an aggregator of company data |

Referenced tests: `test_candidates.py::test_R2_5_R2_6_R2_7_R2_8_R2_9_R2_31_R2_34_R2_35_rendered_text_and_metadata`, `test_candidates.py::test_R2_6_R2_7_R2_8_R2_41_R2_42_R2_43_RL66_fraction_offset_and_default_kind`, `test_harness.py::test_R2_5_R2_6_R2_7_R2_8_RL66_controlled_provider_serves_metadata_variants`

### R2.7
- Section: Page kind and publication time
- Package: P5
- Status: open
- Text:

  > | `Published: <RFC 3339 timestamp>` | When the page was published |

Referenced tests: `test_candidates.py::test_R2_5_R2_6_R2_7_R2_8_R2_9_R2_31_R2_34_R2_35_rendered_text_and_metadata`, `test_candidates.py::test_R2_6_R2_7_R2_8_R2_41_R2_42_R2_43_RL66_fraction_offset_and_default_kind`, `test_harness.py::test_R2_5_R2_6_R2_7_R2_8_RL66_controlled_provider_serves_metadata_variants`

### R2.8
- Section: Page kind and publication time
- Package: P5
- Status: open
- Text:

  > A page with no `Kind` line, or with a value not listed above, is of kind `own` when the
  > host of its URL, normalised as `stage-1.md` normalises a domain, is the company's domain,
  > and of kind `aggregator` otherwise. A page with no `Published` line, or with a value that is not an RFC 3339 timestamp, has no
  > publication time.

Referenced tests: `test_candidates.py::test_R2_5_R2_6_R2_7_R2_8_R2_9_R2_31_R2_34_R2_35_rendered_text_and_metadata`, `test_candidates.py::test_R2_6_R2_7_R2_8_R2_41_R2_42_R2_43_RL66_fraction_offset_and_default_kind`, `test_harness.py::test_R2_5_R2_6_R2_7_R2_8_RL66_controlled_provider_serves_metadata_variants`

### R2.9
- Section: Page text
- Package: P5
- Status: open
- Text:

  > From this stage, a page's **text** is the text a browser shows once the page has loaded,
  > without clicking controls. Activating disclosure controls is not required. The graded
  > corpus contains no facts that require a click to reveal them.
  > Evidence (§4) is read from page text so defined, and a citation's excerpt must appear in the
  > page's text. A citation's `provider` is the provider that served the text the excerpt was
  > copied from.

Referenced tests: `test_candidates.py::test_R2_5_R2_6_R2_7_R2_8_R2_9_R2_31_R2_34_R2_35_rendered_text_and_metadata`, `test_harness.py::test_R2_9_R2_10_R2_23_controlled_provider_serves_distinct_browser_text`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.10
- Section: Web access
- Package: P5
- Status: open
- Text:

  > From this stage an extract through `nimble` may ask Nimble to load the page in a browser and
  > serve the text the browser shows once the page has loaded, with no control activated:
  > `provider_options={"render": True}` on WebRouter's extract.

Referenced tests: `test_harness.py::test_R2_9_R2_10_R2_23_controlled_provider_serves_distinct_browser_text`

### R2.11
- Section: Web access
- Package: P5
- Status: open
- Text:

  > Two optional browser vendors are also available, in addition to the providers in §2:

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.12
- Section: Web access
- Package: P5
- Status: open
- Text:

  > - `kernel`, through `open_browser`;

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.13
- Section: Web access
- Package: P5
- Status: open
- Text:

  > - `browserbase`, through `open_browser` and `browse`.

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.14
- Section: Web access
- Package: P5
- Status: open
- Text:

  > A service may use Nimble's rendered extract alone to obtain every page's browser text;
  > neither browser vendor is required.

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.15
- Section: Web access
- Package: P5
- Status: open
- Text:

  > The deployment provides these environment variables in addition to those in §2:

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.16
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | `KERNEL_API_KEY` | Credential for the `kernel` provider |

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.17
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | `KERNEL_BASE_URL` | Base URL of the `kernel` provider endpoint |

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.18
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | `BROWSERBASE_API_KEY` | Credential for the `browserbase` provider |

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.19
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | `BROWSERBASE_BASE_URL` | Base URL of the `browserbase` provider endpoint |

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.20
- Section: Web access
- Package: P5
- Status: open
- Text:

  > WebRouter reads the keys from the environment. A service that uses these vendors passes their
  > base URLs to WebRouter in `provider_config`, beside those of §2:

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.21
- Section: Web access
- Package: P5
- Status: open
- Text:

  > ```python
  > provider_config={"kernel": {"base_url": <KERNEL_BASE_URL>},
  >                  "browserbase": {"base_url": <BROWSERBASE_BASE_URL>}}
  > ```

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.22
- Section: Web access
- Package: P5
- Status: open
- Text:

  > These calls cost, in the units of §9:

Referenced tests: `test_rate_limits.py::test_R2_22_R2_23_R2_28_R2_30_RL61_refusal_spacing_and_logged_cost`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.23
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Extract through `nimble` that loads the page in a browser | 3 per URL requested, including a URL for which no page is returned |

Referenced tests: `test_harness.py::test_R2_9_R2_10_R2_23_controlled_provider_serves_distinct_browser_text`, `test_rate_limits.py::test_R2_22_R2_23_R2_28_R2_30_RL61_refusal_spacing_and_logged_cost`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.24
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Open a session through `kernel` | 0 |

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`, `test_rate_limits.py::test_R2_24_R2_25_R2_28_R2_29_exhausted_optional_sessions_do_not_block_build`

### R2.25
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Open a session through `browserbase` | 2 |

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`, `test_rate_limits.py::test_R2_24_R2_25_R2_28_R2_29_exhausted_optional_sessions_do_not_block_build`

### R2.26
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Each page served to a session, through either | 1 |

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.27
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Browse run through `browserbase` | 4 |

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`

### R2.28
- Section: Web access
- Package: P5
- Status: open
- Text:

  > A failed open, a failed page load and releasing a session cost nothing.

Referenced tests: `test_rate_limits.py::test_R2_22_R2_23_R2_28_R2_30_RL61_refusal_spacing_and_logged_cost`, `test_rate_limits.py::test_R2_24_R2_25_R2_28_R2_29_exhausted_optional_sessions_do_not_block_build`, `test_rate_limits.py::test_R2_28_R2_29_idle_optional_provider_sessions_expire_after_one_minute`

### R2.29
- Section: Web access
- Package: P5
- Status: open
- Text:

  > Each provider keeps at most 4 sessions open at once; opening another is answered with an
  > error. A session that no client has been connected to for 60 seconds is closed by the
  > provider.

Referenced tests: `test_candidates.py::test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_20_R2_21_R2_24_R2_25_R2_26_R2_27_R2_29_optional_browser_vendor_costs`, `test_rate_limits.py::test_R2_24_R2_25_R2_28_R2_29_exhausted_optional_sessions_do_not_block_build`, `test_rate_limits.py::test_R2_28_R2_29_idle_optional_provider_sessions_expire_after_one_minute`

### R2.30
- Section: Rate limits
- Package: P5
- Status: open
- Text:

  > From this stage a provider may answer any call with 429. A call answered 429 costs nothing
  > (`stage-1.md` §9). The same call (the same provider, operation and arguments) made again less
  > than one second after a 429 for it was answered is answered 429 again. No call is answered
  > 429 more than three times in a row, except that opening a session while its provider keeps
  > 4 open (Web access) is answered 429 until one of them closes. Time a build spends waiting to
  > make a call again after a 429 does not count toward the 10 seconds of `stage-1.md` §8.

Referenced tests: `test_rate_limits.py::test_R2_22_R2_23_R2_28_R2_30_RL61_refusal_spacing_and_logged_cost`

### R2.31
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > A **candidate** is one value for one field, supported by one excerpt of one page. Every
  > value that a page of the evidence (§4) supports for a field is a candidate of that field,
  > once for each such page. The evidence now also holds the page that each research claim of
  > the evidence cites, whether or not the citation supports its claim: a build reads that page
  > as it reads any other. A research claim whose citation does not support it is still not a
  > candidate. A candidate's `provider` is a provider that served the text
  > its excerpt is taken from; when several did, any of them may be given.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_candidates.py::test_R2_5_R2_6_R2_7_R2_8_R2_9_R2_31_R2_34_R2_35_rendered_text_and_metadata`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.32
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > Each field gains `candidates`:

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`

### R2.33
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > ```json
  > {
  >   "value": "Dana Ruiz",
  >   "status": "contested",
  >   "citations": [ { "url": "https://acme-robotics.test/about", "excerpt": "...", "provider": "nimble" } ],
  >   "candidates": [
  >     { "value": "Dana Ruiz", "url": "https://acme-robotics.test/about",
  >       "excerpt": "Dana Ruiz has led Acme Robotics as chief executive since 2021.",
  >       "provider": "nimble", "kind": "own",
  >       "published_at": "2026-01-10T00:00:00+00:00",
  >       "retrieved_at": "2026-03-01T09:00:00+00:00", "selected": true },
  >     { "value": "Sam Ortiz", "url": "https://bizdata.test/acme-robotics",
  >       "excerpt": "Acme Robotics CEO: Sam Ortiz.",
  >       "provider": "tavily", "kind": "aggregator",
  >       "published_at": "2026-02-20T00:00:00+00:00",
  >       "retrieved_at": "2026-03-01T09:00:00+00:00", "selected": false }
  >   ]
  > }
  > ```

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`

### R2.34
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `url`, `excerpt` and `provider` follow the citation rules in §4.

Referenced tests: `test_candidates.py::test_R2_5_R2_6_R2_7_R2_8_R2_9_R2_31_R2_34_R2_35_rendered_text_and_metadata`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.35
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `kind` is the page's kind, and `published_at` its publication time or null. Only an
  >   imported candidate (below) has a null `kind`; it has the authority of `aggregator`.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_candidates.py::test_R2_5_R2_6_R2_7_R2_8_R2_9_R2_31_R2_34_R2_35_rendered_text_and_metadata`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.36
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `retrieved_at` is the time of the build that gathered the candidate (§8, Builds).

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_candidates.py::test_R2_36_R2_38_failed_refresh_keeps_last_ready_candidates`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.37
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `selected` is true on exactly one candidate of a field that has candidates, the one the
  >   rule picks, and false on the others.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.38
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `candidates` lists the candidates of the last build that completed `ready`, in the order
  >   the selection rule ranks them, the selected one first. A field with no candidate has
  >   `"candidates": []` and is `unknown`.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_candidates.py::test_R2_36_R2_38_failed_refresh_keeps_last_ready_candidates`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.39
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - Two values are the same value when they are equal as JSON values; strings are compared
  >   exactly, after removing surrounding whitespace.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`

### R2.40
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > Rank a field's candidates, highest first, by:

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.41
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > 1. **Authority** of the page's kind: `own` and `filing` rank equal and highest, then `news`,
  >    then `aggregator`.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_candidates.py::test_R2_6_R2_7_R2_8_R2_41_R2_42_R2_43_RL66_fraction_offset_and_default_kind`

### R2.42
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > 2. **Recency** within the same authority: the later `published_at` ranks higher. A candidate
  >    without a publication time ranks below every candidate of the same authority that has one.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_candidates.py::test_R2_6_R2_7_R2_8_R2_41_R2_42_R2_43_RL66_fraction_offset_and_default_kind`

### R2.43
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > 3. **URL**: when authority and publication time are equal, the candidate whose `url` is
  >    smaller, comparing the strings by Unicode code point, ranks higher; between two
  >    candidates with the same URL, they rank by provider in the order `nimble`, `tavily`,
  >    `kernel`, `browserbase`.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_candidates.py::test_R2_6_R2_7_R2_8_R2_41_R2_42_R2_43_RL66_fraction_offset_and_default_kind`

### R2.44
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > 4. **Value**: between two candidates with the same URL and provider, the one whose value is
  >    smaller ranks higher: integers compare as numbers, strings by Unicode code point after
  >    removing surrounding whitespace.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`

### R2.45
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > The highest-ranked candidate is the selected one. The field's `value` is the selected
  > candidate's value, and its `citations` are the `url`, `excerpt` and `provider` of every
  > candidate with that value, in rank order.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.46
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > A candidate of lower authority is selected only when no candidate of higher authority
  > exists for that field. The rule runs over all of a field's candidates.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`

### R2.47
- Section: Status
- Package: P6
- Status: open
- Text:

  > `status` is now one of three values:

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`, `test_sample_evidence.py::test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost`

### R2.48
- Section: Status
- Package: P6
- Status: open
- Text:

  > | `known` | The field has candidates, and they all have the same value |

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`

### R2.49
- Section: Status
- Package: P6
- Status: open
- Text:

  > | `contested` | The field's candidates carry two or more different values |

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`

### R2.50
- Section: Status
- Package: P6
- Status: open
- Text:

  > | `unknown` | The field has no candidate; `value` is null |

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`

### R2.51
- Section: Status
- Package: P6
- Status: open
- Text:

  > A `contested` field still has a selected `value` and its citations.

Referenced tests: `test_candidates.py::test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence`

### R2.52
- Section: Status
- Package: P6
- Status: open
- Text:

  > `GET /dossiers` (§8) is unchanged. The `legal_name` it lists is the selected value.

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.53
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > The following screens must be reachable by URL. Other screens must be reachable through the UI.
  > Server-side and client-side rendering are both permitted.

Referenced tests: `test_browser.py::test_R2_53_R2_55_R2_56_R2_57_R2_58_R2_59_R2_60_RL63_html_and_api_negotiation`, `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`

### R2.54
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/` | The dossier list with search, and a form to research a domain |

Referenced tests: `test_browser.py::test_R2_54_R2_57_R2_71_R2_72_R2_73_R2_78_R2_94_R2_102_empty_not_found_and_refused_research`, `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`, `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.55
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/dossiers/{domain}` | One dossier: its state, its six fields with their values, status and citations, a refresh and a reload |

Referenced tests: `test_browser.py::test_R2_53_R2_55_R2_56_R2_57_R2_58_R2_59_R2_60_RL63_html_and_api_negotiation`, `test_browser.py::test_R2_55_R2_63_failed_dossier_has_a_distinct_state`, `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.56
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/dossiers/{domain}/evidence` | Every candidate of every field of that dossier |

Referenced tests: `test_browser.py::test_R2_53_R2_55_R2_56_R2_57_R2_58_R2_59_R2_60_RL63_html_and_api_negotiation`, `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.57
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/contested` | Every contested field across all dossiers |

Referenced tests: `test_browser.py::test_R2_53_R2_55_R2_56_R2_57_R2_58_R2_59_R2_60_RL63_html_and_api_negotiation`, `test_browser.py::test_R2_54_R2_57_R2_71_R2_72_R2_73_R2_78_R2_94_R2_102_empty_not_found_and_refused_research`, `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.58
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/signup` | Signup |

Referenced tests: `test_browser.py::test_R2_53_R2_55_R2_56_R2_57_R2_58_R2_59_R2_60_RL63_html_and_api_negotiation`, `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`

### R2.59
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/login` | Login |

Referenced tests: `test_browser.py::test_R2_53_R2_55_R2_56_R2_57_R2_58_R2_59_R2_60_RL63_html_and_api_negotiation`, `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`

### R2.60
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > The browser and the API share `/dossiers/{domain}`. Return the UI for `Accept: text/html`;
  > API requests without that header receive JSON. `/`, `/dossiers/{domain}/evidence` and
  > `/contested` are browser routes; they read the API's dossier data. The domain in a browser
  > route is normalised as in §4.

Referenced tests: `test_browser.py::test_R2_53_R2_55_R2_56_R2_57_R2_58_R2_59_R2_60_RL63_html_and_api_negotiation`

### R2.61
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > The UI must expose the `data-testid` attributes listed below for integration testing. Additional
  > elements are permitted, and the visual implementation is the team's choice subject to the
  > product-quality requirements below.

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.62
- Section: Product and visual direction
- Package: P7a/P7b
- Status: open
- Text:

  > The browser experience must feel like a coherent, presentation-ready research product, not a
  > thin wrapper of raw controls. Aim for a calm, legible, evidence-first character: a reader
  > opening a dossier should see at a glance which fields are known, which are unknown and which
  > are contested, and where each value came from.

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.63
- Section: Product and visual direction
- Package: P7a/P7b
- Status: open
- Text:

  > A field's value and its status must be the clearest information on the dossier screen, with
  > its citations directly beside it. Fields, citations, candidates and contested fields should be
  > easy to scan, and status, provider, page kind and publication time should be understandable
  > without interpreting raw API data. Use a consistent visual system for typography, spacing,
  > colour, controls and feedback. Primary actions — research, refresh — must be easy to identify.
  > Known, unknown, contested, building, failed, loading, successful, refused and uncertain states
  > must be visually distinct as well as satisfying the behavioural requirements below. Format
  > names, years, headcount ranges, money and timestamps for people first; expose technical
  > identifiers only where they help the user. Each citation shows its excerpt as quoted text and
  > links to its URL.

Referenced tests: `test_browser.py::test_R2_55_R2_63_failed_dossier_has_a_distinct_state`, `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`, `test_browser_faults.py::test_R2_63_loading_state_screenshot_with_delayed_dossier_read`

### R2.64
- Section: Product and visual direction
- Package: P7a/P7b
- Status: open
- Text:

  > The required flows must remain clear and usable at a 375 CSS-pixel viewport and at conventional
  > desktop widths, without horizontal page scrolling. Inputs need visible labels, keyboard focus must
  > be apparent, and text and controls need sufficient contrast. Provide considered empty, loading and
  > error states, and keep navigation consistent across the required routes. A custom illustration,
  > brand asset or exact visual match to a reference is not required.

Referenced tests: `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`, `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.65
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `signup-email`, `signup-password`, `signup-display-name` | Inputs |

Referenced tests: `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`

### R2.66
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `signup-submit` | Button |

Referenced tests: `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`

### R2.67
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `login-email`, `login-password`, `login-submit` | Inputs and button |

Referenced tests: `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`

### R2.68
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `auth-error` | Error message. Present only when there is one |

Referenced tests: `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`

### R2.69
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `current-user` | Visible on every screen when signed in. Text contains the display name |

Referenced tests: `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`, `test_upgrade.py::test_R2_69_R2_93_R2_108_RL59_browser_session_survives_stage1_import`

### R2.70
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `logout-button` | Button |

Referenced tests: `test_browser.py::test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout`

### R2.71
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `research-domain` | Input for the domain to research |

Referenced tests: `test_browser.py::test_R2_54_R2_57_R2_71_R2_72_R2_73_R2_78_R2_94_R2_102_empty_not_found_and_refused_research`, `test_browser_faults.py::test_R2_71_R2_72_R2_79_R2_107_existing_dossier_created_by_another_client_does_not_rebuild`, `test_browser_faults.py::test_R2_71_R2_72_R2_73_R2_74_R2_79_R2_103_R2_106_research_lost_response_reuses_key`

### R2.72
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `research-submit` | Button. Sends `POST /dossiers` |

Referenced tests: `test_browser.py::test_R2_54_R2_57_R2_71_R2_72_R2_73_R2_78_R2_94_R2_102_empty_not_found_and_refused_research`, `test_browser_faults.py::test_R2_71_R2_72_R2_79_R2_107_existing_dossier_created_by_another_client_does_not_rebuild`, `test_browser_faults.py::test_R2_71_R2_72_R2_73_R2_74_R2_79_R2_103_R2_106_research_lost_response_reuses_key`

### R2.73
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `research-error` | Error message, when the request is refused — including an invalid domain |

Referenced tests: `test_browser.py::test_R2_54_R2_57_R2_71_R2_72_R2_73_R2_78_R2_94_R2_102_empty_not_found_and_refused_research`, `test_browser_faults.py::test_R2_71_R2_72_R2_73_R2_74_R2_79_R2_103_R2_106_research_lost_response_reuses_key`

### R2.74
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `research-uncertain` | Shown when the outcome of a research request is unknown (below) |

Referenced tests: `test_browser_faults.py::test_R2_71_R2_72_R2_73_R2_74_R2_79_R2_103_R2_106_research_lost_response_reuses_key`, `test_upgrade.py::test_R2_74_R2_79_R2_92_R2_106_R2_108_lost_stage1_write_retries_after_import`

### R2.75
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `dossier-search` | Input. Filters the list as `q` does on `GET /dossiers` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.76
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `dossier-list` | Container. Children ordered by domain ascending |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.77
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `dossier-item-{domain}` | One per listed dossier. Carries `data-state="{state}"`. Text contains the domain, and the legal name when known. Links to `/dossiers/{domain}` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.78
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `empty-dossiers` | Shown instead of the list when no dossier matches |

Referenced tests: `test_browser.py::test_R2_54_R2_57_R2_71_R2_72_R2_73_R2_78_R2_94_R2_102_empty_not_found_and_refused_research`

### R2.79
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > A research request that succeeds, with 202 or 200, opens `/dossiers/{domain}` for the
  > normalised domain. A domain that already has a dossier, including one created by another
  > client after this browser read the list, opens that dossier and starts no build.

Referenced tests: `test_browser_faults.py::test_R2_71_R2_72_R2_79_R2_107_existing_dossier_created_by_another_client_does_not_rebuild`, `test_browser_faults.py::test_R2_71_R2_72_R2_73_R2_74_R2_79_R2_103_R2_106_research_lost_response_reuses_key`, `test_upgrade.py::test_R2_74_R2_79_R2_92_R2_106_R2_108_lost_stage1_write_retries_after_import`

### R2.80
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-domain` | Text is exactly the normalised domain |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.81
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-state` | Text is exactly `building`, `ready` or `failed` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.82
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-spent` | Formatted `spent_units`. Carries `data-units="{integer}"` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.83
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-researched-at` | Text contains `researched_at`, formatted. Absent when it is null |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.84
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `field-{field}` | One per field, six in all, in the order of the table in `stage-1.md` §4. Carries `data-status="{status}"` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.85
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `field-value-{field}` | The formatted value. Carries `data-value` (below). Present only when the value is not null |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.86
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `field-contested-{field}` | A marker. Present only when the field is `contested` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.87
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `field-citations-{field}` | Container of the field's citations, in API order |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.88
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `citation-{field}-{n}` | The field's `n`th citation, counting from 1. Text contains the excerpt. Contains a link whose `href` is the citation's `url`. Carries `data-provider="{provider}"` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.89
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-evidence-link` | Link to `/dossiers/{domain}/evidence` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.90
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-refresh` | Button. Sends `POST /dossiers/{domain}/refresh` |

Referenced tests: `test_browser_faults.py::test_R2_90_R2_91_R2_92_R2_103_R2_106_refresh_lost_response_reuses_key`, `test_browser_faults.py::test_R2_90_R2_91_confirmed_refresh_refusal_is_not_uncertain`, `test_browser_faults.py::test_R2_90_R2_96_R2_103_R2_105_browser_follows_another_clients_refresh`

### R2.91
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `refresh-error` | Error message, when a refresh is refused |

Referenced tests: `test_browser_faults.py::test_R2_90_R2_91_R2_92_R2_103_R2_106_refresh_lost_response_reuses_key`, `test_browser_faults.py::test_R2_90_R2_91_confirmed_refresh_refusal_is_not_uncertain`

### R2.92
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `refresh-uncertain` | Shown when the outcome of a refresh is unknown (below) |

Referenced tests: `test_browser_faults.py::test_R2_90_R2_91_R2_92_R2_103_R2_106_refresh_lost_response_reuses_key`, `test_upgrade.py::test_R2_74_R2_79_R2_92_R2_106_R2_108_lost_stage1_write_retries_after_import`

### R2.93
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-reload` | Button. Reads the dossier again without starting a build |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`, `test_browser_faults.py::test_R2_93_R2_103_R2_104_latest_reload_wins_over_delayed_earlier_read`, `test_browser_faults.py::test_R2_93_R2_96_R2_104_stale_build_poll_cannot_overwrite_ready`, `test_upgrade.py::test_R2_69_R2_93_R2_108_RL59_browser_session_survives_stage1_import`

### R2.94
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-not-found` | Shown instead of the fields when no dossier exists for the domain |

Referenced tests: `test_browser.py::test_R2_54_R2_57_R2_71_R2_72_R2_73_R2_78_R2_94_R2_102_empty_not_found_and_refused_research`

### R2.95
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > `data-value` is the API value as text: a string value unchanged, an integer in plain decimal
  > digits.

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.96
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > While the dossier's state is `building`, the screen reads the dossier again at least every
  > 2 seconds until the state is `ready` or `failed`, and then shows the new fields without a
  > manual reload.

Referenced tests: `test_browser_faults.py::test_R2_90_R2_96_R2_103_R2_105_browser_follows_another_clients_refresh`, `test_browser_faults.py::test_R2_93_R2_96_R2_104_stale_build_poll_cannot_overwrite_ready`

### R2.97
- Section: Evidence — `/dossiers/{domain}/evidence`
- Package: P7b
- Status: open
- Text:

  > | `evidence-{field}` | One container per field, six in all. Children in API `candidates` order |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.98
- Section: Evidence — `/dossiers/{domain}/evidence`
- Package: P7b
- Status: open
- Text:

  > | `candidate-{field}-{n}` | The field's `n`th candidate, counting from 1. Text contains the formatted value and the excerpt. Carries `data-value`, `data-provider`, `data-kind`, `data-url`, `data-published-at` (the RFC 3339 `published_at`, empty when null) and `data-selected="true"` or `"false"` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.99
- Section: Evidence — `/dossiers/{domain}/evidence`
- Package: P7b
- Status: open
- Text:

  > | `evidence-empty-{field}` | Shown instead of candidates when the field has none |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.100
- Section: Contested fields — `/contested`
- Package: P7b
- Status: open
- Text:

  > | `contested-list` | Container. Children ordered by domain ascending, then by field in the order of the table in `stage-1.md` §4 |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.101
- Section: Contested fields — `/contested`
- Package: P7b
- Status: open
- Text:

  > | `contested-item-{domain}-{field}` | One per contested field of any dossier. Carries `data-value` for the selected value. Text contains the domain, the field and every distinct candidate value. Links to `/dossiers/{domain}/evidence` |

Referenced tests: `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.102
- Section: Contested fields — `/contested`
- Package: P7b
- Status: open
- Text:

  > | `empty-contested` | Shown instead of the list when no field is contested |

Referenced tests: `test_browser.py::test_R2_54_R2_57_R2_71_R2_72_R2_73_R2_78_R2_94_R2_102_empty_not_found_and_refused_research`, `test_browser.py::test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested`

### R2.103
- Section: Refresh and competing clients
- Package: P7a
- Status: open
- Text:

  > After any successful action, the data on the same page must show the new state without a manual
  > reload. Navigation must wait for the write to succeed before it refreshes the data. Any mechanism
  > is fine, including a full navigation. Apart from the reading while a dossier is `building`,
  > there is no live-update requirement: another client may change state, but this browser need
  > only read again after its own action, an explicit reload or a build it is waiting on.

Referenced tests: `test_browser_faults.py::test_R2_71_R2_72_R2_73_R2_74_R2_79_R2_103_R2_106_research_lost_response_reuses_key`, `test_browser_faults.py::test_R2_90_R2_91_R2_92_R2_103_R2_106_refresh_lost_response_reuses_key`, `test_browser_faults.py::test_R2_93_R2_103_R2_104_latest_reload_wins_over_delayed_earlier_read`, `test_browser_faults.py::test_R2_90_R2_96_R2_103_R2_105_browser_follows_another_clients_refresh`

### R2.104
- Section: Refresh and competing clients
- Package: P7a
- Status: open
- Text:

  > - `dossier-reload` reads the dossier again. **Latest read wins:** a delayed earlier read must
  >   not overwrite a later one, including when responses arrive out of order. This applies to the
  >   reads while a dossier is `building` as well.

Referenced tests: `test_browser_faults.py::test_R2_93_R2_103_R2_104_latest_reload_wins_over_delayed_earlier_read`, `test_browser_faults.py::test_R2_93_R2_96_R2_104_stale_build_poll_cannot_overwrite_ready`

### R2.105
- Section: Refresh and competing clients
- Package: P7a
- Status: open
- Text:

  > - Another client may refresh a dossier after this browser reads it. A refresh from this
  >   browser while that build runs is answered 202 like any other and the screen follows the
  >   running build to its end.

Referenced tests: `test_browser_faults.py::test_R2_90_R2_96_R2_103_R2_105_browser_follows_another_clients_refresh`

### R2.106
- Section: Refresh and competing clients
- Package: P7a
- Status: open
- Text:

  > - If a research or refresh response is lost, including after the request commits, show
  >   `research-uncertain` or `refresh-uncertain` (nonempty text), not `research-error` or
  >   `refresh-error`. Keep the request retryable with the **same key and body**. A successful
  >   retry removes both the error and the uncertainty elements, shows the dossier, and starts at
  >   most one build. Unknown outcomes are not confirmed refusals.

Referenced tests: `test_browser_faults.py::test_R2_71_R2_72_R2_73_R2_74_R2_79_R2_103_R2_106_research_lost_response_reuses_key`, `test_browser_faults.py::test_R2_90_R2_91_R2_92_R2_103_R2_106_refresh_lost_response_reuses_key`, `test_upgrade.py::test_R2_74_R2_79_R2_92_R2_106_R2_108_lost_stage1_write_retries_after_import`

### R2.107
- Section: Refresh and competing clients
- Package: P7a
- Status: open
- Text:

  > No background polling beyond the reading while `building`, live synchronization, or recovery
  > across page reloads is required.

Referenced tests: `test_browser_faults.py::test_R2_71_R2_72_R2_79_R2_107_existing_dossier_created_by_another_client_does_not_rebuild`

### R2.108
- Section: Existing clients after an upgrade
- Package: P6
- Status: open
- Text:

  > A stage-2 service must accept an export produced by the same team's stage-1 service. A browser
  > signed in before that export/import upgrade must remain signed in afterwards. Imported dossiers
  > appear in the list and on their screens. Each imported field gains one candidate for every
  > value that text the providers served to the dossier's last stage-1 build that completed
  > `ready` supports for that field (`stage-1.md` §4), once for each page whose served text
  > supports it. The candidate's excerpt is taken from that text and supports the value; its
  > `provider` is the provider that served that text, its `kind` and `published_at` are as the
  > exported state records them or else null, and its `retrieved_at` is the dossier's
  > `researched_at`. Each imported field's `value`, `status` and `citations` then follow from its
  > candidates by the selection rule and Status, as after a build. A research or refresh
  > request whose response was lost before export remains retryable after import with the same body and key; the UI must recover the original response
  > and show the imported dossier. These requirements apply when import completes between browser
  > requests; migration during an in-flight request is not required. No page reload or new screen
  > is required.

Referenced tests: `test_harness.py::test_R2_108_upgrade_bridge_routes_api_before_and_after_switch`, `test_upgrade.py::test_R2_108_R2_109_RL59_stage1_export_sessions_and_candidates_survive_upgrade`, `test_upgrade.py::test_R2_69_R2_93_R2_108_RL59_browser_session_survives_stage1_import`, `test_upgrade.py::test_R2_74_R2_79_R2_92_R2_106_R2_108_lost_stage1_write_retries_after_import`

### R2.109
- Section: Existing clients after an upgrade
- Package: P6
- Status: open
- Text:

  > The candidates of an imported dossier are replaced by those of its next completed build.

Referenced tests: `test_upgrade.py::test_R2_108_R2_109_RL59_stage1_export_sessions_and_candidates_survive_upgrade`
