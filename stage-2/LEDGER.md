# Dossier — Requirements Ledger (cumulative)

Stage 1 opened: 2026-11-19T20:44Z. Source: spec/stage-1.md (quoted verbatim below).
Statuses: `open` → `built` → `tested` → `accepted`. Lead updates statuses from verdicts.

## Layout (stage-1/, a complete buildable service)

```
stage-1/
  Dockerfile  RUN.md  requirements.txt  LEDGER.md
  app/        P1 + P3 (builder-a): HTTP server, auth, control endpoints, store, idempotency, dossier API, build lifecycle
  engine/     P2 + P4 (builder-b): Appendix A support rules, research/gather engine (the only code that talks to providers, via web_router)
```
Tests live OUTSIDE the stage folders, at repo root `qa/stage-1/`:
`qa/stage-1/unit_app/` (builder-a), `qa/stage-1/unit_engine/` (builder-b), `qa/stage-1/accept/` (prover). No test, harness or fault tooling inside `stage-N/`.

Language: Python 3.12, single process, in-memory state guarded by locks (no multi-worker server). webrouter is called in-process.

## Engine interface (contract between app/ and engine/)

```python
# engine/__init__.py  (builder-b owns)
def run_build(domain: str, *, budget: int = 80, on_spend=None, cancelled=None) -> BuildResult
#  domain: normalised domain. on_spend(units:int) is called right after every provider call that costs units
#  (so the app can keep spent_units current). cancelled: optional callable -> bool, polled between calls.
#  Never raises; blocking; thread-safe (many builds run concurrently).
# BuildResult: .ok (bool: False iff NO provider call succeeded), .spent (int units, total of the build),
#   .fields: dict for all six field names ->
#     {"value": <str|int|None>, "citations": [{"url","excerpt","provider"}]}   (value None => citations [])
```
Until engine/ lands, builder-a uses a local stub (`app/_stub_engine.py`, try/except ImportError) returning ok=True, all-unknown, spent=0.

## Packages

| Pkg | Owner | Area | Ledger scope | Order |
|---|---|---|---|---|
| P1 | builder-a | Dockerfile, RUN.md, requirements, server skeleton, health, reset, clock, errors/conventions, auth, export/import, limits | F entries | 1st — must build and start first (target < 60 min) |
| P2 | builder-b | `engine/support.py`: Appendix A as pure functions (sentences, supports, candidates, normalisation) + unit tests | S entries | 1st (parallel with P1) |
| P3 | builder-a | Dossier API: idempotency, POST /dossiers, GET, refresh, list, build lifecycle (single build, reset/import safety, spent_units) | D entries | after P1 |
| P4 | builder-b | `engine/` research: web_router calls, budget accounting, discovery, extraction, research run, field decision, fault tolerance | R entries | after P2 |
| PQ | prover | `qa/stage-1/accept/`: black-box acceptance tests from the spec + an independent Appendix A oracle, mock-web driven | all | parallel from the start |
| G | gatekeeper | review, merge, check runs | — | as packages land |

## Rulings

- **RL1 Check order on idempotent writes.** (1) bearer auth → 401; (2) `Idempotency-Key` absent/empty → 400 `missing_idempotency_key`; (3) key longer than 255 → 422; (4) `POST /dossiers` only: body must parse as a JSON object, else 400 `malformed_request` (refresh ignores its body entirely, even if unparseable); (5) path domain for refresh normalised/validated (422) — but a claimed key is resolved first for refresh as well; (6) an already-claimed key for the same (user, method, path-as-written) is resolved (replay 200 / 409) BEFORE field validation; (7) field validation (400 wrong type, 422 invalid); (8) execution. Only successful (2xx) outcomes claim a key; a 4xx never does ("treated as a first use").
- **RL2 Idempotency identity.** Record key = (user_id, method, path exactly as written, key). Request body identity = the parsed JSON value restricted to the known field (`domain` for POST /dossiers, compared as the raw string, no normalisation), unknown fields dropped. Same key, same path, different identity → 409. Same key on a different path → independent. A replay returns **200** with the stored original body (even when the original was 202 or 200) and starts nothing. Concurrent identical requests: one normal response, the rest 200 with the same body; implement under a lock so the operation takes effect once.
- **RL3 Failed build.** `failed` iff no provider call of that build succeeded (at least one call answered without error ⇒ `ready`, possibly with every field unknown). A failed build leaves fields, `researched_at` unchanged, `spent_units` still counts any units spent. All-providers-erroring build ⇒ `failed`, spent 0, ends well inside 10 s (webrouter retries/backoff must be bounded so error answers do not delay the build).
- **RL4 Search accounting.** Every build makes exactly ONE search answered without error whose query is exactly the normalised domain (nimble `lite`, 1 unit; if it errors, retry through nimble once and/or fall back to tavily `lite`, 8 units, until one answers). All other searches use other queries that name the company (e.g. `"<Name> headquarters city"`, `"<Name> CEO chief executive"`, `"<Name> founded year"`, `"<Name> employees headcount"`, `"<Name> funding raised"`, `"<Name> legal name registered"`), `<Name>` = first label with `-` as space, title-cased. Never repeat the exact-domain query after one succeeded.
- **RL5 Cost accounting.** The engine reserves units BEFORE each call so that the build can never exceed 80: worst case is counted (calls that may time out cost full units). A refused call (error status) costs 0; a timeout/connection failure costs full table price; an extract costs 1 (nimble) / 2 (tavily) per URL requested, whether or not a page returns; research start costs 25 (nimble), polls free. `spent_units` in the API = the sum of what the engine reports via on_spend over all builds since creation. Extract through nimble never sets `render`.
- **RL6 Discovery strategy (guidance, not a mandate).** Cheapest full text is nimble `extract` (1/URL, whole served text, also for non-searchable pages). Plan: nimble `lite` searches (1 each) for the domain query + ~6 other queries to discover up to ~50 distinct URLs, start the nimble research run (25) with all six field names as output-schema properties, then extract (1/URL) the discovered URLs most likely to be the company's pages and the research citation URLs, ranked by (url host is the company domain, result rank). Stay ≤ 80 with the reserve rule; prefer breadth (recall of supporting pages) because a field is `known` exactly when the evidence supports a value. Tavily is optional and never required.
- **RL7 Deciding a value.** Candidates come from (a) every sentence of every gathered page's prose, tested with the Appendix A support rule, and (b) research claims whose citation excerpt supports the claimed value (a claim is asserted only then; the excerpt must also be verified as a whitespace-normalised substring of the prose served for that page, extracting that page if needed; a claim whose citation does not support is discarded). Several different values for a field: choose the value with the most distinct supporting pages, ties → a page whose host is the company domain, then lexicographically smallest value for determinism. Cite 1–3 supporting excerpts from distinct pages, each a single sentence supporting exactly the chosen value, copied verbatim (whitespace runs may collapse), 1–500 chars, from prose, `provider` = the provider that served that text.
- **RL8 Email.** Emails are compared case-insensitively (signup uniqueness, login, fixture duplicate check); the user's email is stored as given. `local@domain` = exactly one `@`, non-empty both sides, no whitespace.
- **RL9 Reset/import generation.** A monotonically increasing state generation; a build thread captures it at start and any write after the generation changed (reset or import) is discarded. Reset/import swap state atomically under the global lock; control calls answer within 10 s.
- **RL10 Export while building.** Export shows a building dossier as it was before the running build (state, fields and researched_at of its last completed build; spent_units as exported); a dossier that never completed a build exports as `failed`, all fields unknown, `researched_at` null. On import the in-flight build does not exist. State JSON must include accounts (hashed passwords), tokens, dossiers, counters (id sequences), idempotency records with original responses; the clock is not part of it.
- **RL11 Unknown routes and methods** answer the §5 envelope (404 `not_found`; 405 may use code `method_not_allowed`) and never 5xx; unhandled exceptions become a 500 envelope only as a last resort and are bugs.
- **RL12 Timings.** All non-build endpoints answer in well under 5 s with 50 concurrent requests on 2 vCPU: password hashing must be cheap enough (scrypt n=2^13 or pbkdf2-sha256 ≥ 100k iterations measured; not bcrypt cost ≥ 12). Builds run in a bounded worker pool; nothing blocks the event loop/handler threads.
- **RL13 Live-provider timing.** Per provider call timeout ≥ 30 s (45 s recommended) and total build wall budget 240 s hard stop (the build still ends `ready`/`failed` ≤ 300 s); never abandon a call waiting < 30 s; do not stop gathering for time within the first 120 s. Against the mock (calls < 1 s) a build must finish ≤ 10 s: run extracts concurrently (a pool of ≤ 8 threads).
- **RL14 Evidence for knownness (ruled on prover's question).** Required knownness comes from §4 evidence only: pages a search can return (searchable != false, served in the current epoch, from ANY corpus company, counting a sentence only if it names the target company) plus nimble research claims whose citation excerpt supports the claimed value. A `searchable: false` page counts only via such a research claim; an unsearchable page with no claim is not required evidence. Conflicts: the service's value must be among the supported values and every citation must support exactly it.
- **RL15 Library packages (P2, engine).** Reviewed on unit + single-defect + differential evidence (vs the prover's oracle) on the commit; the build-and-start gate runs on the integrated tree after P1 is accepted and P2 merged. Verdict form `ACCEPT (library, unit-level; integration build confirmed after merge)`.
- **RL16 Fixture users.** Signup rules (8-char password, local@domain email, display_name <= 100) do NOT apply to fixture users. Fixture password may be any string incl. empty; login with it is 200, wrong password 401. User fields must be strings (wrong type 400); missing field, empty/>64-char id, duplicate id or case-insensitive duplicate email: 422, nothing changes. `now` required RFC 3339 with offset (missing/invalid 422, wrong type 400); missing `users` = none, non-list 400; unparseable/non-object body 400. Reset may move the clock backwards; only POST /_test/clock is monotonic.
- **RL17 Import validation.** Import validates the whole state structurally before swapping it in (under the lock): all exported sections present with right types, tokens refer to existing users, ids unique, counters >= highest issued id, dossier field shape (known => citations, unknown => none). `{}` is invalid. Missing/non-object `state`, wrong track/format_version: 422; unparseable or non-object body: 400. Nothing changes on rejection.
- **RL18 P1 rejection rulings (37affec).** Reset of up to 500 users <= 10 s (parallel scrypt, ~n=2^12, no lazy/plaintext hashing; 500 users <= 5 s). Clock parse is exact RFC 3339: any fractional digits compared exactly, offset Z or +-HH:MM with HH 00-23 MM 00-59, valid ranges. Bodies up to 64 MiB accepted (unknown fields ignored), above that 413 `payload_too_large`. Import: counters non-negative < 10^30, ids 1-64 chars, stored password records well-formed scrypt with sane parameters; login can never 5xx. Lone surrogates in a body/string: 400 `malformed_request` at parse; response encoding never raises; catch-all 500 envelope is a last resort and a bug. Every claimed id named in an individual test name/docstring with an index per test module.
- **RL19 Engine recall under 80 units.** Keep the cap; extract priority: research citation URLs, company-host URLs, URLs whose title/snippet name the company, then by query count/rank. A lite snippet shorter than 300 chars is the whole prose (no extract needed); longer snippets only contribute sentences complete inside the snippet. Citations are always verbatim substrings of text the provider served for that URL. Keep the research run (25). Report recall (knowable vs known fields, units) on all sample companies with each engine handoff; target 100% of knowable fields.
- **RL20 (amends RL18).** Fixture-user passwords hashed with real scrypt n=2^10 (signup/login n=2^13, parameters stored in the record). Body cap 16 MiB (above: 413 `payload_too_large` envelope, never 400/5xx). Counters bound 10^12 accepted. Lone-surrogate strings are valid JSON: stored and echoed, never 5xx, export->import round-trips identically, `q` with one is fine. Declared test gaps need real tests.
- **RL21 Engine evidence and long sentences (P4).** Decisions use (a) pages returned by some search of the build (full served text) and (b) supported research-claim excerpts. A page gathered only because research cites it contributes only the supported claimed excerpt for the claimed field; its other sentences are not evidence. A sentence over 500 chars may be cited by a verbatim contiguous word-boundary sub-span of <= 500 chars that supports V on its own provided the full sentence also supports V (shortest such span starting at the sentence start); a late negation or conflicting second value keeps the field unknown.
- **RL22 P3 rejection rulings (c2c42b6).** (1) Export/import and last completed build (R1.125, R1.126, R1.128): a dossier tracks the outcome of its last completed build separately from whether a build is running. States: `ready` (fields and `researched_at` of that build), `failed` (fields and `researched_at` kept from the last `ready` build, or null with all unknown if none), `building`. A `failed` dossier may carry fields and a non-null `researched_at`; import must accept it and an unchanged export must always import. An export taken during a build holds the dossier as the last completed build left it (ready, then failed refresh, then running refresh exports `failed` with the prior fields); a never-completed dossier exports `failed`, all unknown. After import no build runs. (2) Reset race (R1.23, R1.129): every state-changing and reading handler authenticates and acts inside one critical section, or re-validates token and state generation inside the transaction; if a reset happened in between the request behaves as if it ran after reset (old token gone: 401 `unauthenticated`, no dossier or idempotency record created). (3) Huge integer query parameters (R1.61, R1.62): never `int()` an unbounded digit string; digits-only regex; plain digits of any length incl. leading zeros are valid; `limit` beyond 200 is 422 even for huge digit strings; `offset` of any length accepted, beyond the total gives an empty page with `has_more` false; oversize request line/query gives a §5 envelope, never 500 or a dropped connection. (4) Import field validation (R1.126, R1.40): each field has exactly `value`, `status`, `citations`; `status` known iff value not null; founded_year and funding_total integers (not booleans), founded_year 1800-2099, funding_total >= 1; headcount_range one of the eight ranges; legal_name/hq_city/ceo non-empty strings without leading/trailing whitespace; known fields have 1+ citations each with non-empty string `url`, `excerpt` 1-500 chars, `provider` nimble or tavily; unknown fields have `citations` []; anything else is 422 and changes nothing. Tests required for each, named with ids.
- **RL23 Process: newest handoff per package.** Superseded hashes are not re-reviewed; the gatekeeper reviews the newest handoff head per package (builder-a d5e580de6a1b34ccdc61cb8d394db40e536a2a13; builder-b 795c4573b3fdf28d4689753f99ed2fe3f5c9407c, P2 and P4 together under RL15), then integrates, runs the event check.
- **RL24 funding_total zero (amends RL22 point 4).** `$0` is an Appendix A amount normalising to whole-dollar integer 0, so `funding_total` is a non-boolean integer >= 0 (import accepts 0; API shows it `known` with citations; null stays unknown). Import ranges must never be narrower than what Appendix A can produce; decision code must not use truthiness tests on values (0 is a value).
- **RL29 Citation provider label (P4).** Every gathered text keeps the provider that actually served it (per source, and per URL if both served it). A citation's `provider` is the provider whose served record contains the excerpt, verified whitespace-normalised against that provider's served prose before emitting; both served -> prefer nimble; never a default. Nimble-search fault + tavily exact-domain search success must yield `tavily` labels. Tests named R1.3, R1.43.
- **RL30 Body cap on every POST route (P1).** 16 MiB cap applies to Content-Length and chunked framing alike, on every POST route: exactly 16 MiB accepted; over -> 413 `payload_too_large` envelope. Draining at most 32 MiB of an oversize body and closing afterwards is an allowed implementation detail.
- **RL31 Digits (Appendix A).** "Digits" in number syntax means ASCII 0-9 only; other Unicode decimal digits are not digits of a number. The prover oracle conforms to this reading (builder-b's ASCII-only behaviour stands).
- **RL32 Export representation vs HTTP shape (clarifies RL22 pt 4, amended by RL24).** The exactly-three-keys rule (`value`, `status`, `citations`) applies to dossier fields in HTTP responses. The opaque export is whatever representation the service chooses (the unchanged export, e.g. `{value, citations}` with `status` derived, must import); import validates semantically the same constraints (status known iff value not null, ranges, citations). Import MUST reject (422 `validation_failed`, state unchanged) legal_name, hq_city, ceo with leading/trailing whitespace. funding_total 0 is VALID per RL24 (prover tests asserting 422 for 0 are stale and must follow RL24).
- **RL33 Process/infra.** The prover's runner must be configurable (resource-name prefix and host port range via environment/CLI) and ship a requirements file; the gatekeeper builds its own venv and runs the suite from the integration branch. Relay-induced latency is a harness artifact: concurrency/timing measures are taken by direct HTTP to the service.
- **RL34 Builder-b defects on 795c457 (RL15/RL18/RL19/RL29).** (a) carry actual provider identity through discovery into citations (RL29); (b) collect the research answer BEFORE bulk extraction so research-citation URLs get first extract priority (RL19); (c) every claimed ledger id appears by name in an individual test name or docstring (RL18; R1.111-R1.116, R1.118, R1.119, R1.136-R1.140, R1.142-R1.146 listed missing); (d) keep the 0313b69 fixes (refused calls cost 0; one successful exact-domain search per build).
- **RL35 Newest heads and RL24 confirmation.** builder-a's newest head is f0d166e3f45dc831fe0619f675c8826173781c10 (descendant of 8b00f50); earlier builder-a hashes are superseded (RL23). RL24 stands: funding_total 0 is valid and known; import accepts 0; negative values stay rejected.
- **RL36 Process: stale prover assertions and extract concurrency.** RL27 stands: resets at instants outside the UTC-representable range return 422 with state unchanged (the prover's old 'build starts' assertions are superseded), and fixture scrypt records outside the two accepted parameter sets ((2^13,8,1) and (2^10,8,1)) are rejected at import with 422. RL13: at most 8 simultaneous extract calls per build (EXTRACT_WORKERS <= 8); the engine needs an independent test for the maximum concurrent extracts and one for a research-only `$0` claim (decision code must not use truthiness).
- **RL37 Harness artifacts.** A client-side `[Errno 9] Bad file descriptor` from a shared httpx client is a harness artifact; burst tests use independent clients or plain sockets. A reset or 5xx seen by a plain-socket client is a service defect.
- **RL38 Review targets (RL23).** P1/P3: builder-a 30efa2ced616d9d6fd38b080431e0b272353b759 (contains f0d166e, 8b00f504, 32daaae; adds RL32 two-key import and whitespace validation). P4: builder-b a29de9e7644a5349daa8d7e999cb7c49c9498578 (base 0313b69 + 26e890f). All earlier hashes (cd5d5cb, 164ea92, 0313b69, e1236a7, 795c457) are superseded and not reviewed or reported against.
- **RL39 Event harness.** The event check may be run unchanged by the gatekeeper (hardcoded `df-*` names are the harness's own); take `/tmp/factory-heavy.lock`, check read-only that no foreign `df-*` resources exist (wait/poll; blocker after 15 minutes), remove only the exact resources the run created. Only on a revision that passed review and the gatekeeper's isolated check.
- **RL42 Body framing.** The 16 MiB cap (413 `payload_too_large`) covers Content-Length and chunked framing. A request with neither header has no body (RFC 9112): a 400 `malformed_request` or the route's own validation envelope is acceptable (never 5xx or reset; server stays healthy). "Without Content-Length" in earlier messages means chunked.
- **RL43 Refusal cost forms.** A refused call costs 0 whether the refusal arrives as an HTTP status or as an SDK error with `status_code=None` and a refusal kind; unanswered calls cost full units. (test gap, closed by builder-b e608a2f.)
- **RL44/RL46 P4 head.** e608a2f3ef5bcaa0842d7a0f4a4f2656700aa99f then 990d0b7fcea33db764d11584f9264a508d9a615c (builder-b) is the review target; earlier P4 hashes are superseded.
- **RL45 Dual-provider texts.** One gathered text per (url, provider); candidates come from every kept text; a citation's provider is the provider whose served text holds the excerpt (nimble when both do). Fixed in 990d0b7.
- **Status log.** P1/P3 builder-a 30efa2ced616d9d6fd38b080431e0b272353b759 ACCEPTED by the gatekeeper (combined P1/P3 review RL14-RL38, RL42). P4 builder-b 990d0b7 under review. Integrated build/start, event check and freeze pending.
- **RL47 R1.121 mock-backed test and R1.135 name.** A build ending `ready` after refused calls that cost 0 and a later answered call is correct under RL3; the mock-backed rate-limit test asserts the mock log (ok == any 200; spend == logged; every 429 costs 0). R1.135 has its own named test.
- **RL48 P4 head.** builder-b 82100ce7da18ecad41b3028e872f565a38937980 (engine code = 990d0b7).
- **RL49 Chunked framing.** Chunk size = ASCII hex digits only; chunk data followed by exactly CRLF; message ends at the blank line after the last chunk; EOF anywhere in the framing is malformed -> 400 `malformed_request`, handler never runs, state unchanged. Valid extensions/trailers parse (204).
- **RL50/RL52 P1/P3 head.** 05d050850d0e6b216bef50319a63fb86f685c3c3 then 13ba6d8093827ac1041dc83fa3801499216d3e00 (builder-a; supersedes 30efa2c and main 3dec36d).
- **RL51 Trailer fields.** A trailer line needs a non-empty RFC 9110 token name, no whitespace before the colon, a colon, no NUL or bare CR in the value; otherwise 400 as RL49.
- **Status log (update).** P4 builder-b 82100ce7da18ecad41b3028e872f565a38937980 ACCEPTED by the gatekeeper (combined P2/P4 review: 114/114 support, 79/79 mock-backed engine, 12/12 sample companies 69/69 values, 32-37 units, five unit-level mutants caught). P1/P3: 30efa2c acceptance withdrawn by RL49/RL51; current target 13ba6d8093827ac1041dc83fa3801499216d3e00 under review. Integrated build/start, event check and freeze pending.
- **RL53 Chunk extensions.** Extensions may be ignored semantically but must follow RFC 9112 chunk-ext grammar (token names, token or closed quoted-string values, BWS); malformed -> 400 as RL49. Materiality rule: after this batch only crashes/5xx/hangs and executed requests that RFC 9112 forbids accepting reopen the stage.
- **RL54 Content-Length.** 1*DIGIT only, no `int()` on unbounded strings; any value > 16 MiB (any length, any leading zeros) -> 413 before the body is read; zero-padded valid values accepted; sign/underscore/0x/empty/duplicate-differing/with-Transfer-Encoding -> 400, never executed.
- **RL55/RL57 P1/P3 head.** 9b72a6949b5a2516d216c70b70e17c1e274153af, then ff5bee577530cd6a912a4a22c25c0c422be2c638 (builder-a); supersedes 13ba6d8 and earlier.
- **RL56 Transfer-Encoding.** Comma list, case-insensitive, all header lines combined; only exactly `chunked` (once) accepted; anything else (not final, repeated, unsupported coding, substring match, empty) -> 400, connection closed, handler never runs.
- **RL58 Pre-existing df-* images.** Evidence: `df-dossier-mockweb:latest` (ID e5c8791be0e4, created 2026-11-18) and `df-harness-runner:latest` (ID 801dad9f311d, created 2026-11-17) predate this run (lock file 2026-11-19); no `df-*` containers or networks exist; both are inert leftovers from earlier runs of the same hardcoded harness names, none created by this room. Ruling: this is not a live collision, so the RL39 15-minute blocker is lifted. The gatekeeper runs the event harness unchanged under the lock without removing those two IDs. Afterwards remove only containers, networks and image IDs the run created; if the harness retagged either name to a new image, retag the original ID back (`docker tag <orig-id> <name>`) and then remove only the new ID. Record the before and after `docker images` listing in the report.
- **Status log (update 2).** P1/P3 builder-a ff5bee577530cd6a912a4a22c25c0c422be2c638 ACCEPTED by the gatekeeper (147 unit tests; prover suite 3af1f508 282/282 on ff5bee5 + 82100ce; five isolated HTTP mutants caught). P4 builder-b 82100ce7da18ecad41b3028e872f565a38937980 ACCEPTED. Integrated build/start, measures M1-M4 on the integrated tree, event check and freeze pending.

## Measures (every revision must be measurable)

- **M1 (spec §1.2, §9)** per-build units ≤ 80, and API `spent_units` == sum of mock `/_mock/log` costs for that dossier: measure with mock log after each build.
- **M2 (§8)** build ends ≤ 10 s with sub-second providers: measure `POST /dossiers` → `ready/failed` wall time on the sample corpus.
- **M3 (§2)** per-request ≤ 5 s (10 s reset/export/import) with 50 in flight; start → /health ≤ 60 s; memory ≤ 3 GiB (docker stats), CPU 2 vCPU.
- **M4 (§4/§8)** exactly one answered exact-domain search per build, and no search answered without error repeating it: measure from mock log (`query == domain` and status 200 count == 1).

## Entries

Status values: open, built, tested, accepted. Spec line numbers refer to spec/stage-1.md.

### R1.1
- Section: Dossier — Stage 1: company profiles
- Spec lines: 5-7
- Package: all / prover
- Status: accepted
- Text:

  > Build from the supplied requirements. Source code, API documentation and schemas from
  > existing products in this domain must not be used.
  > WebRouter's own documentation may be used.

### R1.2
- Section: 1. Scope
- Spec lines: 16-16
- Package: all / prover
- Status: accepted
- Text:

  > The following apply to all operations, including concurrent requests and retries:

### R1.3
- Section: 1. Scope
- Spec lines: 18-20
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > 1. Every value the service asserts cites at least one excerpt that a provider endpoint served
  >    to this service, and that excerpt supports the value. No citation is invented, reworded, or
  >    attached to a value it does not support.

### R1.4
- Section: 1. Scope
- Spec lines: 21-21
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > 2. No build of a dossier spends more than 80 units (§9).

### R1.5
- Section: 1. Scope
- Spec lines: 23-23
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > Contact data, people search, and fields other than the six in §4 are out of scope.

### R1.6
- Section: 2. Delivery and deployment
- Spec lines: 27-29
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Deliver an HTTP service, a `Dockerfile` and a `RUN.md` with a command that builds and
  > starts the service without manual setup. Language, framework and storage are unrestricted.
  > A `docker-compose.yml` is optional.

### R1.7
- Section: 2. Delivery and deployment
- Spec lines: 31-35
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > The submission is a containerized HTTP service, not a Python package. Python is not
  > required in the implementation. TypeScript/JavaScript, Go, Rust, Java, Python and any
  > other language are equally valid. The submitted `Dockerfile` is built and started,
  > and only its HTTP behavior is exercised; it does not import or execute the
  > submission's source files on the host that runs it.

### R1.8
- Section: 2. Delivery and deployment
- Spec lines: 37-39
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > The image must run on its own with `-e PORT=<port>` and a port mapping. All runtime
  > dependencies, initialization and seed data must work within that single container. Compose
  > configuration is not used to start the service.

### R1.9
- Section: Web access
- Spec lines: 43-46
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > Two providers are available: `nimble` and `tavily`. Nimble is the default provider: every
  > service must be able to research companies using Nimble alone. Tavily is optional: a service
  > may use it beside Nimble, and its absence must not prevent research while Nimble answers.
  > The live submission and optional live judging provide a working Nimble key only.

### R1.10
- Section: Web access
- Spec lines: 48-52
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > The service reaches the providers only through WebRouter, the Python package `webrouter`
  > (module `web_router`). The service may be written in any language, but every request to a
  > provider goes through `web_router`: called in-process, or from a Python helper process that
  > the service runs inside its own container. The stage folder's dependency manifest lists
  > `webrouter>=0.12.0`. Calling a provider's API by any other route is not permitted.

### R1.11
- Section: Web access
- Spec lines: 53-57
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Install it and the provider SDK dependencies from PyPI, including in the service's Docker build:
  >
  > ```sh
  > pip install "webrouter[search,extract,research]>=0.12.0"
  > ```

### R1.12
- Section: Web access
- Spec lines: 60-68
- Package: P1 foundation (builder-a)
- Status: accepted
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

### R1.13
- Section: Web access
- Spec lines: 70-76
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > Keys are opaque non-empty strings. WebRouter's `nimble` provider reads `NIMBLE_API_KEY` and
  > `NIMBLE_BASE_URL` from the environment, and its `tavily` provider reads `TAVILY_API_KEY`. A
  > service that uses Tavily passes its base URL to WebRouter in `provider_config`:
  >
  > ```python
  > provider_config={"tavily": {"api_base_url": <TAVILY_BASE_URL>}}
  > ```

### R1.14
- Section: Resource limits
- Spec lines: 84-85
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | CPU | 2 vCPU |
  > | Memory | 3 GiB |

### R1.15
- Section: Resource limits
- Spec lines: 86-86
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | Start to first healthy response | 60 s |

### R1.16
- Section: Resource limits
- Spec lines: 87-87
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | Concurrent requests | up to 50 in flight |

### R1.17
- Section: Resource limits
- Spec lines: 88-88
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | Per-request timeout | 5 s (10 s for `POST /_test/reset`) |

### R1.18
- Section: Resource limits
- Spec lines: 89-89
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Outbound network | available during `docker build`; at run time, **only the provider endpoints this specification lists** |

### R1.19
- Section: Resource limits
- Spec lines: 90-90
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | Disk | ephemeral; state need not survive a container restart |

### R1.20
- Section: Resource limits
- Spec lines: 92-94
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Runtime assets and dependencies must be included in the image. This includes fonts,
  > scripts and stylesheets; external services other than the provider endpoints this
  > specification lists are unavailable at runtime.

### R1.21
- Section: 3.1 Listening
- Spec lines: 100-100
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Listen on `0.0.0.0` using the `PORT` environment variable, default `8080`.

### R1.22
- Section: 3.2 Health
- Spec lines: 108-110
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Return 200 once the service and its data store can serve requests, within 60 seconds
  > of container start. Non-200 responses are permitted before the service is ready.
  > `/health` makes no provider call.

### R1.23
- Section: 3.3 Reset and seed
- Spec lines: 123-127
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Replace all service state with the fixture in the request body (§4). When reset returns
  > 204, subsequent requests must see only that fixture: no users other than the seeded ones,
  > no dossiers and no stored idempotent responses. Repeated resets are supported. A build
  > still running when reset is called must not change the state that follows the reset.
  > This control endpoint must be enabled in the delivered image and requires no authentication.

### R1.24
- Section: 3.4 Clock
- Spec lines: 131-132
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > The service keeps a clock that only reset and `POST /_test/clock` move. Every timestamp
  > the service records or returns is read from this clock.

### R1.25
- Section: 3.4 Clock
- Spec lines: 143-144
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - Reset sets the clock to the fixture's `now`. Before the first reset the clock follows the
  >   system time.

### R1.26
- Section: 3.4 Clock
- Spec lines: 145-146
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - The clock stands still between calls: two requests with no clock call between them read
  >   the same time.

### R1.27
- Section: 3.4 Clock
- Spec lines: 147-148
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - `now` is an RFC 3339 timestamp with an explicit offset. A `now` earlier than the clock's
  >   current time is 422 `validation_failed` and changes nothing.

### R1.28
- Section: 3.4 Clock
- Spec lines: 149-149
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - `POST /_test/clock` requires no authentication.

### R1.29
- Section: 3.5 Conventions
- Spec lines: 153-153
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - Requests and responses are `application/json; charset=utf-8`.

### R1.30
- Section: 3.5 Conventions
- Spec lines: 154-154
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - Timestamps in responses are RFC 3339 with an explicit offset, e.g. `2026-09-24T19:00:00+02:00`.

### R1.31
- Section: 3.5 Conventions
- Spec lines: 155-155
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - Unknown fields in a request body are ignored, never an error.

### R1.32
- Section: 3.5 Conventions
- Spec lines: 156-156
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - Unknown query parameters are ignored.

### R1.33
- Section: 3.5 Conventions
- Spec lines: 157-157
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - IDs are opaque strings of at most 64 characters. Their format is yours.

### R1.34
- Section: Users
- Spec lines: 163-163
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Users sign up and log in (§6). Every authenticated user sees the same dossiers.

### R1.35
- Section: Domains
- Spec lines: 167-172
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > A company is identified by its domain. Every domain the API takes, in a body or a path, is
  > first **normalised**: surrounding whitespace removed, lowercased, one trailing `.` removed,
  > and one leading `www.` removed. The normalised domain must then be a valid host name: two or
  > more labels separated by `.`, each label 1 to 63 characters of `a-z`, `0-9` and `-`, not
  > starting or ending with `-`, and 253 characters or fewer in total. Anything else, including a
  > URL with a scheme or a path, is 422 `validation_failed`.

### R1.36
- Section: Domains
- Spec lines: 174-175
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > `Acme-Robotics.TEST.`, `www.acme-robotics.test` and `acme-robotics.test` name the same
  > company and the same dossier. Responses always carry the normalised domain.

### R1.37
- Section: Fields
- Spec lines: 179-179
- Package: all / prover
- Status: accepted
- Text:

  > A dossier has exactly these six fields:

### R1.38
- Section: Fields
- Spec lines: 183-188
- Package: all / prover
- Status: accepted
- Text:

  > | `legal_name` | String: the company's registered name, e.g. `Acme Robotics, Inc.` |
  > | `hq_city` | String: the city of the company's headquarters, without region or country, e.g. `Lisbon` |
  > | `ceo` | String: the full name of the company's chief executive, e.g. `Dana Ruiz` |
  > | `founded_year` | Integer: the year the company was founded, e.g. `2014` |
  > | `headcount_range` | String: one of `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+` |
  > | `funding_total` | Integer: total equity funding raised, in whole US dollars, e.g. `12000000` |

### R1.39
- Section: Fields
- Spec lines: 190-192
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > A string value is written as the supporting excerpt writes it, without surrounding
  > whitespace. A headcount the web states as a number, or as a range that fits inside one of
  > the ranges above, has the range that contains it as its value.

### R1.40
- Section: Fields
- Spec lines: 194-207
- Package: P3 dossier API (builder-a)
- Status: accepted
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

### R1.41
- Section: Evidence and support
- Spec lines: 211-213
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > The **evidence** for a company is every page that some search, through any provider and for
  > any query naming the company (as in Appendix A.2), returns, with its full text, and every
  > claim that a `nimble` research run for the company asking for all six fields answers with.

### R1.42
- Section: Evidence and support
- Spec lines: 215-218
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > Of the searches that a provider answers without an error, every build makes exactly one whose
  > query is exactly the company's normalised domain, through a provider of its choice; its other
  > such searches use other queries. A search that a provider answers with an error does not
  > count. The pages whose text a build obtains from providers are the pages it **gathers**.

### R1.43
- Section: Evidence and support
- Spec lines: 220-224
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > A **citation** is an excerpt of text a provider served for the page at `url`:
  >
  > - The excerpt is copied character for character from that served text, except that any run
  >   of whitespace may be written as a single space. It is 1 to 500 characters long.
  > - It is taken from the page's prose (below), not from its header.

### R1.44
- Section: Evidence and support
- Spec lines: 226-230
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > An excerpt **supports** a value when, read on its own, it states that value for that field
  > of this company, as Appendix A defines. The excerpt may write the value differently from the
  > API: `Acme Robotics has raised $12M.` and `Acme Robotics has raised 12 million dollars.` both
  > support a `funding_total` of `12000000`, and `Acme Robotics employs about 120 people.`
  > supports a `headcount_range` of `51-200`.

### R1.45
- Section: Evidence and support
- Spec lines: 232-234
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > A research answer carries a claimed value for a field and a citation for the claim. The
  > claim is asserted only when its citation supports it. A field is `unknown` when no evidence
  > supports a value for it, even when a research answer claims one.

### R1.46
- Section: Evidence and support
- Spec lines: 236-237
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > When the evidence supports more than one value for a field, the field holds one of them and
  > cites only excerpts that support that value.

### R1.47
- Section: Pages
- Spec lines: 241-249
- Package: P2 support rules (builder-b)
- Status: accepted
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

### R1.48
- Section: Fixture format
- Spec lines: 251-268
- Package: P1 foundation (builder-a)
- Status: accepted
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

### R1.49
- Section: 5. Errors
- Spec lines: 272-272
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Every 4xx and 5xx response carries this body:

### R1.50
- Section: 5. Errors
- Spec lines: 278-279
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Use the specified HTTP status and `code`. The human-readable `message` may use any wording.
  > Endpoint-specific errors are listed with each endpoint.

### R1.51
- Section: 5. Errors
- Spec lines: 283-283
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | 400 | `malformed_request` | Unparseable body, or a field of the wrong JSON type |

### R1.52
- Section: 5. Errors
- Spec lines: 284-284
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | 400 | `missing_idempotency_key` | Required `Idempotency-Key` header absent or empty |

### R1.53
- Section: 5. Errors
- Spec lines: 285-285
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | 401 | `unauthenticated` | Missing, malformed or unknown bearer token |

### R1.54
- Section: 5. Errors
- Spec lines: 286-286
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | 404 | `not_found` | No such resource, or not visible to this caller |

### R1.55
- Section: 5. Errors
- Spec lines: 287-287
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | 409 | `idempotency_key_reuse` | Key already used by this caller with a different request body |

### R1.56
- Section: 5. Errors
- Spec lines: 288-288
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | 422 | `validation_failed` | A required field or query parameter is missing, or a stated rule is violated with no more specific code |

### R1.57
- Section: 5. Errors
- Spec lines: 290-291
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > A field of the correct JSON type with an invalid format or out-of-range value gives
  > 422 `validation_failed`, unless an endpoint specifies a different error. In addition:

### R1.58
- Section: 5. Errors
- Spec lines: 293-295
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > - An integer-valued **query parameter** is written as plain decimal digits: `1e9`, `4.0` and `+4`
  >   are 422 `validation_failed` whatever their numeric value.
  > - Reserve 400 `malformed_request` for a body that does not parse or a field of the wrong type.

### R1.59
- Section: 5. Errors
- Spec lines: 297-297
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Shared ranges, enforced on every endpoint that takes them:

### R1.60
- Section: 5. Errors
- Spec lines: 301-301
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | `Idempotency-Key` | 1 to 255 characters | 422 `validation_failed` |

### R1.61
- Section: 5. Errors
- Spec lines: 302-303
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | `limit` | integer 1 to 200 | 422 `validation_failed` |
  > | `offset` | integer 0 or more | 422 `validation_failed` |

### R1.62
- Section: 5. Errors
- Spec lines: 305-306
- Package: all / prover
- Status: accepted
- Text:

  > Requests must not produce 5xx responses, including under concurrent load and when a
  > provider endpoint answers with an error.

### R1.63
- Section: 6. Authentication
- Spec lines: 310-311
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Authentication supports signup and login. Email verification, password reset, refresh
  > tokens and role-management endpoints are out of scope.

### R1.64
- Section: 6. Authentication
- Spec lines: 313-325
- Package: P1 foundation (builder-a)
- Status: accepted
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

### R1.65
- Section: 6. Authentication
- Spec lines: 329-333
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > | Email already registered | 409 `email_taken` |
  > | Password shorter than 8 characters | 422 `validation_failed` |
  > | `email` not of the form `local@domain` | 422 `validation_failed` |
  > | `display_name` empty or longer than 100 characters | 422 `validation_failed` |
  > | Wrong password or unknown email on login | 401 `unauthenticated` |

### R1.66
- Section: 6. Authentication
- Spec lines: 335-335
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > For a user seeded by the fixture (§3.3), `user_id` is that user's `id` in the fixture.

### R1.67
- Section: 6. Authentication
- Spec lines: 337-339
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Every other endpoint requires a bearer token, except `/health`, the `/_test/*` endpoints and
  > the two above. A request to such an endpoint that lacks a valid token is 401
  > `unauthenticated`, even when it also lacks a required `Idempotency-Key`.

### R1.68
- Section: 6. Authentication
- Spec lines: 341-343
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > ```http
  > Authorization: Bearer <token>
  > ```

### R1.69
- Section: 6. Authentication
- Spec lines: 345-345
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Tokens do not expire. An account may have multiple valid tokens and concurrent sessions.

### R1.70
- Section: 6. Authentication
- Spec lines: 347-348
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Passwords must be stored using a password-hashing function such as bcrypt, scrypt or
  > Argon2, or an equivalent. Plaintext password storage is not permitted.

### R1.71
- Section: 7. Idempotency
- Spec lines: 352-354
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > Two write paths require an idempotency key (§8): **`POST /dossiers`** and
  > **`POST /dossiers/{domain}/refresh`**. Everything below applies to each of them
  > independently.

### R1.72
- Section: 7. Idempotency
- Spec lines: 360-361
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > The key is scoped to **the authenticated user**. Two different users may use the same key string
  > with no interaction between them.

### R1.73
- Section: 7. Idempotency
- Spec lines: 363-366
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > A replay means the same user sending the **same method, the same path and the same body**. The
  > same key with the same body on a different path is a different request, not a replay, and must
  > succeed normally. `Acme-Robotics.test` and `acme-robotics.test` in a path or body are different
  > requests for this rule, though they name the same dossier.

### R1.74
- Section: 7. Idempotency
- Spec lines: 370-370
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | Header absent or empty | 400 `missing_idempotency_key` |

### R1.75
- Section: 7. Idempotency
- Spec lines: 371-371
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | First use of the key | The normal response (§8) |

### R1.76
- Section: 7. Idempotency
- Spec lines: 372-372
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | Replay: same key, same body | **200**, body identical to the original response as a JSON value |

### R1.77
- Section: 7. Idempotency
- Spec lines: 373-373
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | Same key, different body | 409 `idempotency_key_reuse` |

### R1.78
- Section: 7. Idempotency
- Spec lines: 374-374
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | Key reused after the original request failed with 4xx | Treated as a first use |

### R1.79
- Section: 7. Idempotency
- Spec lines: 376-380
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > "Same body" means the same JSON value after parsing — key order and whitespace do not matter.
  > Unknown fields are ignored (§3.5) and play no part in this comparison: a body that differs
  > from the first only in unknown fields is the same body, so the request is a replay.
  > `POST /dossiers/{domain}/refresh` takes no body; any body sent to it is ignored and plays no
  > part in deciding a replay.

### R1.80
- Section: 7. Idempotency
- Spec lines: 382-383
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > For concurrent identical requests with an unused key, exactly one returns the normal
  > response. The others return 200 with the same body. The operation takes effect only once.

### R1.81
- Section: 7. Idempotency
- Spec lines: 385-386
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > A successful replay returns the original response, even after the dossier has changed. It
  > starts no build and makes no provider call.

### R1.82
- Section: 7. Idempotency
- Spec lines: 388-390
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > After the body has parsed as a JSON object and the caller is authenticated, an already
  > claimed key is resolved before field validation. Thus changing a successful request to an
  > invalid body with the same key still returns `409 idempotency_key_reuse`.

### R1.83
- Section: Builds
- Spec lines: 396-399
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > A **build** researches one dossier: it calls the providers, decides each field, and replaces
  > the dossier's fields with the result when it completes. A dossier's first build starts with
  > `POST /dossiers`, and every later one with `POST /dossiers/{domain}/refresh`. A build's
  > **time** is the clock's time when the request that started it was received.

### R1.84
- Section: Builds
- Spec lines: 401-401
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - A dossier has at most one build running at a time.

### R1.85
- Section: Builds
- Spec lines: 402-403
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - A build ends in `ready` when it completed, or `failed` when none of its provider calls
  >   succeeded. A failed build leaves the fields as they were.

### R1.86
- Section: Builds
- Spec lines: 404-405
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > - When a build completes `ready`, each field is `known` exactly when the evidence (§4)
  >   supports a value for it.

### R1.87
- Section: Builds
- Spec lines: 406-407
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > - A build whose provider calls each answer within one second ends within 10 seconds of the
  >   request that started it.

### R1.88
- Section: Builds
- Spec lines: 408-412
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > - That bound is not a deadline for slower providers. Against the live providers
  >   (`NIMBLE_BASE_URL` unset, or its host `sdk.nimbleway.com`), where a Nimble search can take
  >   over ten seconds and a research run about a minute, a build does not give up on a call
  >   that has been waiting less than 30 seconds, nor stop gathering because of the time it has
  >   run in its first 120 seconds. It still ends `ready` or `failed` within 300 seconds.

### R1.89
- Section: Builds
- Spec lines: 413-414
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - Reading a dossier, listing dossiers and every other request except `POST /dossiers` and
  >   `POST /dossiers/{domain}/refresh` make no provider call.

### R1.90
- Section: `POST /dossiers`
- Spec lines: 418-418
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > **An idempotent write path.** `Idempotency-Key` is required; see §7.

### R1.91
- Section: `POST /dossiers`
- Spec lines: 420-431
- Package: P3 dossier API (builder-a)
- Status: accepted
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

### R1.92
- Section: `POST /dossiers`
- Spec lines: 433-435
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > When no dossier exists for the domain, the service creates one, starts its first build and
  > returns 202. When a dossier already exists for the domain, the service starts no build and
  > returns **200** with that dossier's `dossier_id`, `domain` and current `state`.

### R1.93
- Section: `POST /dossiers`
- Spec lines: 437-438
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > Concurrent requests for the same domain create one dossier and start one build, whatever
  > their keys.

### R1.94
- Section: `POST /dossiers`
- Spec lines: 442-443
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | `domain` missing | 422 `validation_failed` |
  > | `domain` invalid after normalisation (§4) | 422 `validation_failed` |

### R1.95
- Section: `GET /dossiers/{domain}`
- Spec lines: 447-463
- Package: P3 dossier API (builder-a)
- Status: accepted
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

### R1.96
- Section: `GET /dossiers/{domain}`
- Spec lines: 465-466
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - `state` is `building` while a build runs, otherwise the outcome of the latest build,
  >   `ready` or `failed`.

### R1.97
- Section: `GET /dossiers/{domain}`
- Spec lines: 467-469
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - `fields` always holds all six fields. Before the first build completes `ready`, every
  >   field is `unknown`. While a later build runs, `fields` are those of the last build that
  >   completed `ready`.

### R1.98
- Section: `GET /dossiers/{domain}`
- Spec lines: 470-470
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - `researched_at` is the time of the last build that completed `ready`, or null.

### R1.99
- Section: `GET /dossiers/{domain}`
- Spec lines: 471-472
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - `spent_units` is the total cost (§9) of every provider call made for this dossier, by
  >   every build, since it was created.

### R1.100
- Section: `GET /dossiers/{domain}`
- Spec lines: 473-473
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - The domain in the path is normalised (§4). No dossier for it is 404 `not_found`.

### R1.101
- Section: `POST /dossiers/{domain}/refresh`
- Spec lines: 477-477
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > **An idempotent write path.** `Idempotency-Key` is required; see §7. No body.

### R1.102
- Section: `POST /dossiers/{domain}/refresh`
- Spec lines: 479-481
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > Starts a new build of the dossier and returns 202 with
  > `{ "dossier_id", "domain", "state": "building" }`. A refresh received while a build of the
  > dossier is running starts no second build and returns 202 with the same body.

### R1.103
- Section: `POST /dossiers/{domain}/refresh`
- Spec lines: 483-484
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > A refresh researches again: its build makes provider calls whether or not anything has
  > changed since the last build, and its spending counts in `spent_units`.

### R1.104
- Section: `POST /dossiers/{domain}/refresh`
- Spec lines: 488-488
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > | No dossier for the domain | 404 `not_found` |

### R1.105
- Section: `GET /dossiers`
- Spec lines: 492-501
- Package: P3 dossier API (builder-a)
- Status: accepted
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

### R1.106
- Section: `GET /dossiers`
- Spec lines: 503-503
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - `legal_name` is the value of the dossier's `legal_name` field, or null.

### R1.107
- Section: `GET /dossiers`
- Spec lines: 504-505
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - `q` is optional. When present, only dossiers whose domain or `legal_name` contains `q`,
  >   compared case-insensitively, are listed. An empty `q` lists every dossier.

### R1.108
- Section: `GET /dossiers`
- Spec lines: 506-506
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - Dossiers are ordered by domain ascending.

### R1.109
- Section: `GET /dossiers`
- Spec lines: 507-508
- Package: P3 dossier API (builder-a)
- Status: accepted
- Text:

  > - `limit` defaults to 50, range 1 to 200. `offset` defaults to 0. `has_more` is true when
  >   items exist beyond the last one returned.

### R1.110
- Section: 9. Providers and cost
- Spec lines: 512-512
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > Each provider call has a cost in **units**:

### R1.111
- Section: 9. Providers and cost
- Spec lines: 516-516
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Search through `nimble`, depth `lite` (title, URL and snippet) | 1 |

### R1.112
- Section: 9. Providers and cost
- Spec lines: 517-517
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Search through `nimble`, depth `fast` (a truncated page body) | 5 |

### R1.113
- Section: 9. Providers and cost
- Spec lines: 518-518
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Search through `nimble`, depth `deep` (the full page) | 15 |

### R1.114
- Section: 9. Providers and cost
- Spec lines: 519-519
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Search through `tavily`, depth `lite` (title, URL and snippet) | 8 |

### R1.115
- Section: 9. Providers and cost
- Spec lines: 520-520
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Search through `tavily`, depth `fast` (title, URL and a longer snippet) | 16 |

### R1.116
- Section: 9. Providers and cost
- Spec lines: 521-521
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Search through `tavily`, depth `deep` (the full page) | 16 |

### R1.117
- Section: 9. Providers and cost
- Spec lines: 522-522
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Extract through `nimble` | 1 per URL requested, including a URL for which no page is returned |

### R1.118
- Section: 9. Providers and cost
- Spec lines: 523-523
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Extract through `tavily` | 2 per URL requested, including a URL for which no page is returned |

### R1.119
- Section: 9. Providers and cost
- Spec lines: 524-524
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > | Research run through `nimble` | 25 when the run is started; checking on or collecting a run costs nothing |

### R1.120
- Section: 9. Providers and cost
- Spec lines: 526-526
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > A search's depth is WebRouter's `search_depth`.

### R1.121
- Section: 9. Providers and cost
- Spec lines: 528-533
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > A search returns at most 10 results, whatever number it asks for. A call that a provider
  > refuses with an error status costs nothing. A call whose answer does not arrive, because it
  > times out or its connection fails, costs its units as in the table, whether or not the
  > provider received it. An extract that the provider answers with no page
  > for the URL is not refused: it costs its units, as in the table, whatever status says so. An
  > extract through `nimble` does not set `render`.

### R1.122
- Section: 9. Providers and cost
- Spec lines: 535-536
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > A build stops making provider calls before its spending would exceed 80 units, and completes
  > with the pages and research claims it has obtained.

### R1.123
- Section: 9. Providers and cost
- Spec lines: 538-539
- Package: P4 research engine (builder-b)
- Status: accepted
- Text:

  > A research request names the company by its domain in its query, and names the fields it
  > asks for by the field names in §4, as the property names of its output schema.

### R1.124
- Section: 10. Export and import
- Spec lines: 543-544
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > The service must support `GET /_test/export` and `POST /_test/import`. Like reset, these
  > are unauthenticated control endpoints.

### R1.125
- Section: 10. Export and import
- Spec lines: 545-548
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Exports may contain credentials and session tokens; handle them as private artifacts.
  > Return 200 from export with a JSON object containing `track: "dossier"`,
  > `format_version: 1` and `state` (an implementation-defined JSON object). The state format
  > is opaque to the caller and must be accepted unchanged by import.

### R1.126
- Section: 10. Export and import
- Spec lines: 550-556
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > Import takes that entire object and atomically replaces the service's state, returning
  > 204. It must accept an unchanged export produced by this service. No dependency on the
  > source process, files, volume, port or network address is allowed. Import is replacement,
  > not merge; repeating it restores the exported state without duplicating anything. Invalid
  > JSON follows §5; missing fields, wrong track/version or an invalid state give 422
  > `validation_failed` without changing the destination. These control calls have a 10-second
  > timeout. Export is an atomic, read-only snapshot; subsequent source writes do not change it.

### R1.127
- Section: 10. Export and import
- Spec lines: 558-566
- Package: P1 foundation (builder-a)
- Status: accepted
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

### R1.128
- Section: 10. Export and import
- Spec lines: 568-570
- Package: P1 foundation (builder-a)
- Status: accepted
- Text:

  > An export taken while a build is running holds the dossier as it was before that build;
  > after import, that dossier is in the state of its last completed build, or `failed` with
  > every field `unknown` when no build had completed.

### R1.129
- Section: 11. Concurrency
- Spec lines: 574-575
- Package: all / prover
- Status: accepted
- Text:

  > Concurrent requests must produce the same results as executing them one at a time in some
  > order. The requirements above hold at every read.

### R1.130
- Section: Appendix A. When an excerpt supports a value
- Spec lines: 579-580
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > This appendix is the whole definition of "supports" used in §4. The service decides support
  > by these rules alone.

### R1.131
- Section: A.1 Sentences
- Spec lines: 584-588
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > A page's prose is split into lines at each line break, and each line into sentences. A
  > sentence ends after a `.`, `!` or `?`, together with any `"`, `”`, `’` or `)` directly after
  > it, when whitespace follows. A `.` that ends one of the legal-form suffixes in A.4, written
  > as a whole word, does not end a sentence. Each sentence is taken without its surrounding
  > whitespace; empty sentences are dropped.

### R1.132
- Section: A.1 Sentences
- Spec lines: 590-591
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > An excerpt is a **single sentence** when, with every run of whitespace written as one space,
  > this rule splits it into exactly one sentence.

### R1.133
- Section: A.2 The rule
- Spec lines: 595-604
- Package: P2 support rules (builder-b)
- Status: accepted
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

### R1.134
- Section: A.2 The rule
- Spec lines: 606-608
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > The company's name, its domain and every phrase are matched without regard to case and as
  > whole words: the characters directly before and after the match are not letters or digits.
  > Phrases with a space match one space.

### R1.135
- Section: A.2 The rule
- Spec lines: 614-614
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `Dana Ruiz has led Acme Robotics as chief executive since 2021.` | `ceo` `Dana Ruiz` |

### R1.136
- Section: A.2 The rule
- Spec lines: 615-615
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `Acme Robotics CEO: Sam Ortiz.` | `ceo` `Sam Ortiz` |

### R1.137
- Section: A.2 The rule
- Spec lines: 616-616
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `Acme Robotics was founded in 2014.` | `founded_year` `2014` |

### R1.138
- Section: A.2 The rule
- Spec lines: 617-617
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `Acme Robotics employs about 120 people.` | `headcount_range` `51-200` |

### R1.139
- Section: A.2 The rule
- Spec lines: 618-618
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `Acme Robotics is reportedly in talks to raise $40M.` | nothing: a negating phrase |

### R1.140
- Section: A.2 The rule
- Spec lines: 619-619
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `Acme Robotics opened a sales office in Porto.` | nothing: no statement phrase for `hq_city` |

### R1.141
- Section: A.3 Phrases
- Spec lines: 625-625
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `legal_name` | `legal name`, `registered name`, `registered as`, `registered company`, `legal entity`, `name of record` |

### R1.142
- Section: A.3 Phrases
- Spec lines: 626-626
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `hq_city` | `headquartered in`, `headquarters in`, `head office in`, `based in`, `registered office in`, `registered seat in` |

### R1.143
- Section: A.3 Phrases
- Spec lines: 627-627
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `ceo` | `chief executive officer`, `chief executive`, `CEO` |

### R1.144
- Section: A.3 Phrases
- Spec lines: 628-628
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `founded_year` | `founded`, `founding`, `established`, `incorporated` |

### R1.145
- Section: A.3 Phrases
- Spec lines: 629-629
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `headcount_range` | `employs`, `employees`, `staff`, `people`, `headcount`, `workforce` |

### R1.146
- Section: A.3 Phrases
- Spec lines: 630-630
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `funding_total` | `raised`, `funding`, `invested`, `investment` |

### R1.147
- Section: A.3 Phrases
- Spec lines: 632-634
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > The negating phrases are: `in talks to`, `plans to`, `planning to`, `wants to`,
  > `expects to`, `hopes to`, `aims to`, `seeking`, `could`, `would`, `might`, `reportedly`,
  > `rumoured`, `former`, `formerly`, `will become`, `not`.

### R1.148
- Section: A.4 Value formats
- Spec lines: 638-641
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > A **capitalised word** is an uppercase letter followed by one or more lowercase letters,
  > with no letter or digit directly before or after it. The letters may be of any alphabet:
  > `Zürich` and `Müller` are capitalised words. An **uppercase word** is two or more uppercase
  > letters, with no letter or digit directly before or after it: `AI`, `USA`.

### R1.149
- Section: A.4 Value formats
- Spec lines: 643-645
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > A **number** is written in digits, optionally with a `,` before each group of three digits
  > and a decimal part after a `.`: `120`, `1,200`, `12.5`, `12,000,000`. Digits directly next to
  > a letter, or joined to other digits by `,` or `.` in any other way, are not a number.

### R1.150
- Section: A.4 Value formats
- Spec lines: 649-649
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `legal_name` | The company's name or its domain (matched as in A.2), then zero or more capitalised or uppercase words each after one space, then an optional `,`, one space, and a legal-form suffix with no letter or digit directly after it. Where several such texts start at the same place, the shortest counts |

### R1.151
- Section: A.4 Value formats
- Spec lines: 650-650
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `hq_city` | A place name directly after a statement phrase for `hq_city` and one space: the longest run of capitalised words joined by single spaces or by `-` that starts there, not part of a longer such run |

### R1.152
- Section: A.4 Value formats
- Spec lines: 651-651
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `ceo` | A person's name: a run of two or three capitalised words joined by single spaces that is not part of a longer such run. Occurrences of the company's name and of the statement phrases for `ceo` are first taken out of the sentence and separate the words around them |

### R1.153
- Section: A.4 Value formats
- Spec lines: 652-652
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `founded_year` | A number of exactly four digits, from 1800 to 2099, that is not part of an amount |

### R1.154
- Section: A.4 Value formats
- Spec lines: 653-653
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `headcount_range` | A number with no decimal part, 1 or more, that is not part of an amount. Words before it, such as `about` or `roughly`, do not change it. A stated range such as `51-200 employees` holds two numbers |

### R1.155
- Section: A.4 Value formats
- Spec lines: 654-654
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `funding_total` | An amount (below) |

### R1.156
- Section: A.4 Value formats
- Spec lines: 656-659
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > The legal-form suffixes, matched exactly as written here: `Inc.`, `Corp.`, `LLC`, `LLP`,
  > `L.P.`, `Ltd`, `Limited`, `Pty Ltd`, `plc`, `PLC`, `GmbH`, `AG`, `KG`, `SE`, `AS`, `A/S`,
  > `ASA`, `AB`, `Oy`, `Oyj`, `B.V.`, `N.V.`, `S.A.`, `S.A.S.`, `S.L.`, `S.r.l.`, `S.p.A.`,
  > `s.r.o.`, `a.s.`, `K.K.`.

### R1.157
- Section: A.4 Value formats
- Spec lines: 661-662
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > An **amount** is written in one of these forms, matched without regard to case, with no
  > letter or digit directly before it or after it:

### R1.158
- Section: A.4 Value formats
- Spec lines: 664-667
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > - `$`, `US$` or `USD`, an optional space, a number, and optionally a scale: `k`, `m`, `mn` or
  >   `bn` directly after the number, or one space and `thousand`, `million` or `billion`.
  >   Examples: `$12M`, `$12.5 million`, `US$12 million`, `USD 12 million`, `$12m`,
  >   `$12,000,000`.

### R1.159
- Section: A.4 Value formats
- Spec lines: 668-669
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > - A number, optionally one space and `thousand`, `million` or `billion`, then one space and
  >   `dollars` or `US dollars`. Examples: `12 million dollars`, `12,000,000 US dollars`.

### R1.160
- Section: A.4 Value formats
- Spec lines: 671-671
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > Amounts in other currencies are not amounts.

### R1.161
- Section: A.5 Normalisation
- Spec lines: 677-677
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `legal_name`, `hq_city`, `ceo` | The text as the excerpt writes it |

### R1.162
- Section: A.5 Normalisation
- Spec lines: 678-678
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `founded_year` | The number as an integer |

### R1.163
- Section: A.5 Normalisation
- Spec lines: 679-679
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `headcount_range` | The range of §4 that contains the number |

### R1.164
- Section: A.5 Normalisation
- Spec lines: 680-680
- Package: P2 support rules (builder-b)
- Status: accepted
- Text:

  > | `funding_total` | The number times the scale (`k` and `thousand` 1,000; `m`, `mn` and `million` 1,000,000; `bn` and `billion` 1,000,000,000) in US dollars. An amount that does not come to a whole number of dollars is not a value |


## Stage 1 freeze

- Frozen product revision: 3bacfc826adb44ecc76d47307eed5a3d9bc63164 (main after P1/P3 ff5bee5, P4 82100ce, P2, prover suite 3af1f508). Later main commits (RL58 ledger b0c962c) differ only in stage-1/LEDGER.md.
- Final acceptance by the gatekeeper: integrated prover suite 282/282; M1-M4 measures passed (12/12 sample builds ready in 0.167-1.333 s, 32-37 units, costs equal provider logs; 50 simultaneous logins all 200, slowest 0.138 s; 33.5 MiB of 3 GiB, 2 CPUs).
- Event check (isolated Stage 1): 122/122 passed, 0 failed, 0 skipped (report: band-work/gatekeeper-rl58-f26e80470eb8/report-2).
- Ledger status at freeze: 164 entries accepted, 0 open.
- Stage 1 frozen: 2026-11-20.

---

# Stage 2 (opened 2026-11-20T06:40Z)

Stage 2 extends a plain copy of frozen stage-1 (3bacfc8). All 164 stage-1 entries above stay in force (regression set); stage-2 entries follow the rulings.

## Stage 2 packages

| Pkg | Owner | Area | Ledger scope | Order |
|---|---|---|---|---|
| P5 | builder-b | `stage-2/engine/`: `selection.py` (pure ranking/status/field assembly), candidates gathering (every supported value per page, research-cited pages read), Kind/Published parsing and defaulting, browser text via nimble `render`, 429 handling, `BuildResult` extended | Page kind, Page text, Web access, Rate limits, Candidates, The selection rule | 1st: `selection.py` + its unit tests first (builder-a imports it), then gathering |
| P6 | builder-a | `stage-2/app/` data model and API: `candidates`, three-valued `status`, `retrieved_at`, `Accept: text/html` negotiation hook, export, import of stage-1 exports, concurrency | preamble item 3, Status, Existing clients after an upgrade, API part of Candidates | 1st (parallel with P5; uses selection.py when it lands, stub until then) |
| P7a | builder-a | `stage-2/app/ui/`: design system (CSS/layout), shell, `/`, `/signup`, `/login`, `/dossiers/{domain}` incl. polling, latest-read-wins, uncertain states, refresh | Screens, Product direction, Signup and login, Dossier list, Dossier, Refresh and competing clients | after P6 skeleton; the shell/layout/CSS module first so P7b can start |
| P7b | builder-b | `stage-2/app/ui/evidence.py`, `contested.py` (own files), using P7a's shell | Evidence, Contested fields | after P5 + P7a shell |
| PQ2 | prover | `qa/stage-2/accept/`: selection oracle, API/candidate tests on the mock web, browser tests of the screens (375 px and desktop, testids), import-of-stage-1-export tests | all | parallel from the start |
| G | gatekeeper | review, UI screenshot review at 375 px and desktop, merges, event checks | | as packages land |

## Stage 2 rulings

- **RL59 Import of a stage-1 export.** The frozen stage-1 export stores no served page text. Import therefore derives candidates from what the export holds: for each known imported field, one candidate per exported citation (value = field value, `url`, `excerpt`, `provider` as cited, `kind` null, `published_at` null, `retrieved_at` = the dossier's `researched_at`), with null kind having aggregator authority. `value`, `status`, `citations` and `candidates` then follow from the selection rule. Unknown fields get `candidates: []`. If the export records kind or published time for a citation, they are used. Import makes no provider call. Known risk: a hidden stage-1 export with several supporting pages is only partly reconstructible; this is the best available reading.
- **RL60 Browser text and cost.** Every excerpt must come from text a browser shows (rendered). Nimble `extract` with `provider_options={"render": True}` costs 3 per URL, so under the 80-unit cap about 20 rendered URLs are affordable. P5 decides which pages to render by evidence value (research-cited URLs and company-host URLs first, as RL19), keeps exactly one exact-domain search per build, never exceeds 80 units, and must read `challenges/dossier/web/README.md` to learn what the mock serves un-rendered versus rendered. Non-rendered text may be used to choose which URLs to render, not as a citation source unless it is proven identical to the browser text. Kernel/browserbase are not used.
- **RL61 Rate limits.** A 429 costs 0. The engine retries the same call no sooner than 1.05 s after the 429 (never a tight loop), at most 3 consecutive 429s are expected, tolerates 429 on any call, and never counts waiting against its working time budget when it measures the 10 s bound. Concurrent extracts may run during another call's wait. A call that stays 429 beyond a bounded number of attempts is treated as an error answer (cost 0).
- **RL62 Selection module contract.** `engine/selection.py` exposes pure functions: `rank(candidates) -> list` (the selection rule exactly), `assemble_field(candidates, retrieved_at) -> {"value","status","citations","candidates"}` (candidate dicts as in the Candidates example, `selected` set, `status` known/contested/unknown, citations of every candidate sharing the selected value in rank order). Same value = JSON equal after stripping surrounding whitespace of strings; ints compare as numbers; bool is not an int. App and import both call it; no second implementation of the rule is allowed anywhere.
- **RL63 Content negotiation and auth in the browser.** `GET /dossiers/{domain}` returns HTML when `Accept` contains `text/html`, else JSON (the API behaviour of stage 1 is unchanged, including 401 for unauthenticated JSON requests). Browser routes `/`, `/dossiers/{domain}` (HTML), `/dossiers/{domain}/evidence`, `/contested`, `/signup`, `/login` are served without authentication as static shells; data is read from the API with the bearer token kept client-side (localStorage), so a token valid before import stays valid after import. Browser routes normalise the domain; an invalid domain shows the not-found state. Assets (fonts, CSS, JS) are inlined or served by the service itself; no external hosts.
- **RL64 Candidate order and selected.** `candidates` lists candidates of the last `ready` build in rank order, selected first; `selected` true only on index 0 of a non-empty list. Candidates are not de-duplicated across pages; the same value from one page yields one candidate per supported (page, value) per RL specification ("once for each such page"); one page may support several different values (one candidate each).
- **RL65 Seat boundaries.** Lead never runs the event harness; gatekeeper does under RL39/RL58. The frozen `stage-1/` folder never changes; test files live in `qa/stage-2/`.
- **RL66 Published parsing.** Same grammar as the stage-1 clock (`parse_rfc3339`): separator `T`/`t`, zone `Z`/`z`, explicit offset required, fractions of any length, ranges checked, leap second :60 accepted; space separator, date-only, no offset and basic form refused; order by exact instant after the offset; `published_at` emitted as written; engine mirrors the grammar and never imports app/.
- **RL67 Merge record.** Stage 2 foundation and ledger 02af420 merged to main as dccbb9c75e6b938af18e252ec2e83174b0381b99; P5 selection.py 04129542 and pages.py ecb5d2d reported by builder-b, not yet reviewed.

## Stage 2 measures (measured on every revision)

- **M5** Cost per build ≤ 80 units with render at 3 units per URL; reported `spent_units` equals the provider log (mock log).
- **M6** Build ends ≤ 10 s with sub-second providers; waits after 429 excluded from the 10 s.
- **M7** Dossier screen re-reads at least every 2 s while `building`; latest read wins.
- **M8** Screens usable at 375 px without horizontal scroll (gatekeeper screenshots).
- **M1-M4** from stage 1 remain: 12 sample builds ready; 50 concurrent logins ≤ 5 s; memory under 3 GiB; 2 CPUs.


## Stage 2 requirements (R2.n) — source spec/stage-2.md, quoted verbatim

Package key: P5 builder-b engine (candidates, Kind/Published, render extract, 429, selection.py); P6 builder-a app data model/API/import; P7a builder-a UI shell, `/`, auth, dossier screen; P7b builder-b evidence and contested screens.

### R2.1
- Section: (preamble)
- Package: P6
- Status: open
- Text:

  > The stage-1 requirements continue to apply, with the additions below. Numbered section
  > references such as §4 and §7 refer to `stage-1.md`.

### R2.2
- Section: (preamble)
- Package: P6
- Status: open
- Text:

  > Sources disagree. A dossier now keeps every value its evidence supports, as candidates, and
  > selects one per field by a fixed rule. Researchers read dossiers, their evidence and the
  > fields in dispute in a browser.

### R2.3
- Section: (preamble)
- Package: P6
- Status: open
- Text:

  > The following applies to all operations, in addition to the stage-1 list:

### R2.4
- Section: (preamble)
- Package: P6
- Status: open
- Text:

  > 3. A field's selected value is the one the selection rule below picks from the field's
  >    candidates; the same candidates always yield the same value.

### R2.5
- Section: Page kind and publication time
- Package: P5
- Status: open
- Text:

  > Two header lines (§4, Pages) now carry requirements:

### R2.6
- Section: Page kind and publication time
- Package: P5
- Status: open
- Text:

  > | `Kind: own`, `Kind: filing`, `Kind: news`, `Kind: aggregator` | The page's **kind**: the company's own site, a filing registry, a news report, or an aggregator of company data |

### R2.7
- Section: Page kind and publication time
- Package: P5
- Status: open
- Text:

  > | `Published: <RFC 3339 timestamp>` | When the page was published |

### R2.8
- Section: Page kind and publication time
- Package: P5
- Status: open
- Text:

  > A page with no `Kind` line, or with a value not listed above, is of kind `own` when the
  > host of its URL, normalised as `stage-1.md` normalises a domain, is the company's domain,
  > and of kind `aggregator` otherwise. A page with no `Published` line, or with a value that is not an RFC 3339 timestamp, has no
  > publication time.

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

### R2.10
- Section: Web access
- Package: P5
- Status: open
- Text:

  > From this stage an extract through `nimble` may ask Nimble to load the page in a browser and
  > serve the text the browser shows once the page has loaded, with no control activated:
  > `provider_options={"render": True}` on WebRouter's extract.

### R2.11
- Section: Web access
- Package: P5
- Status: open
- Text:

  > Two optional browser vendors are also available, in addition to the providers in §2:

### R2.12
- Section: Web access
- Package: P5
- Status: open
- Text:

  > - `kernel`, through `open_browser`;

### R2.13
- Section: Web access
- Package: P5
- Status: open
- Text:

  > - `browserbase`, through `open_browser` and `browse`.

### R2.14
- Section: Web access
- Package: P5
- Status: open
- Text:

  > A service may use Nimble's rendered extract alone to obtain every page's browser text;
  > neither browser vendor is required.

### R2.15
- Section: Web access
- Package: P5
- Status: open
- Text:

  > The deployment provides these environment variables in addition to those in §2:

### R2.16
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | `KERNEL_API_KEY` | Credential for the `kernel` provider |

### R2.17
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | `KERNEL_BASE_URL` | Base URL of the `kernel` provider endpoint |

### R2.18
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | `BROWSERBASE_API_KEY` | Credential for the `browserbase` provider |

### R2.19
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | `BROWSERBASE_BASE_URL` | Base URL of the `browserbase` provider endpoint |

### R2.20
- Section: Web access
- Package: P5
- Status: open
- Text:

  > WebRouter reads the keys from the environment. A service that uses these vendors passes their
  > base URLs to WebRouter in `provider_config`, beside those of §2:

### R2.21
- Section: Web access
- Package: P5
- Status: open
- Text:

  > ```python
  > provider_config={"kernel": {"base_url": <KERNEL_BASE_URL>},
  >                  "browserbase": {"base_url": <BROWSERBASE_BASE_URL>}}
  > ```

### R2.22
- Section: Web access
- Package: P5
- Status: open
- Text:

  > These calls cost, in the units of §9:

### R2.23
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Extract through `nimble` that loads the page in a browser | 3 per URL requested, including a URL for which no page is returned |

### R2.24
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Open a session through `kernel` | 0 |

### R2.25
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Open a session through `browserbase` | 2 |

### R2.26
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Each page served to a session, through either | 1 |

### R2.27
- Section: Web access
- Package: P5
- Status: open
- Text:

  > | Browse run through `browserbase` | 4 |

### R2.28
- Section: Web access
- Package: P5
- Status: open
- Text:

  > A failed open, a failed page load and releasing a session cost nothing.

### R2.29
- Section: Web access
- Package: P5
- Status: open
- Text:

  > Each provider keeps at most 4 sessions open at once; opening another is answered with an
  > error. A session that no client has been connected to for 60 seconds is closed by the
  > provider.

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

### R2.32
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > Each field gains `candidates`:

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

### R2.34
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `url`, `excerpt` and `provider` follow the citation rules in §4.

### R2.35
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `kind` is the page's kind, and `published_at` its publication time or null. Only an
  >   imported candidate (below) has a null `kind`; it has the authority of `aggregator`.

### R2.36
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `retrieved_at` is the time of the build that gathered the candidate (§8, Builds).

### R2.37
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `selected` is true on exactly one candidate of a field that has candidates, the one the
  >   rule picks, and false on the others.

### R2.38
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - `candidates` lists the candidates of the last build that completed `ready`, in the order
  >   the selection rule ranks them, the selected one first. A field with no candidate has
  >   `"candidates": []` and is `unknown`.

### R2.39
- Section: Candidates
- Package: P5 (engine) / P6 (API shape)
- Status: open
- Text:

  > - Two values are the same value when they are equal as JSON values; strings are compared
  >   exactly, after removing surrounding whitespace.

### R2.40
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > Rank a field's candidates, highest first, by:

### R2.41
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > 1. **Authority** of the page's kind: `own` and `filing` rank equal and highest, then `news`,
  >    then `aggregator`.

### R2.42
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > 2. **Recency** within the same authority: the later `published_at` ranks higher. A candidate
  >    without a publication time ranks below every candidate of the same authority that has one.

### R2.43
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > 3. **URL**: when authority and publication time are equal, the candidate whose `url` is
  >    smaller, comparing the strings by Unicode code point, ranks higher; between two
  >    candidates with the same URL, they rank by provider in the order `nimble`, `tavily`,
  >    `kernel`, `browserbase`.

### R2.44
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > 4. **Value**: between two candidates with the same URL and provider, the one whose value is
  >    smaller ranks higher: integers compare as numbers, strings by Unicode code point after
  >    removing surrounding whitespace.

### R2.45
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > The highest-ranked candidate is the selected one. The field's `value` is the selected
  > candidate's value, and its `citations` are the `url`, `excerpt` and `provider` of every
  > candidate with that value, in rank order.

### R2.46
- Section: The selection rule
- Package: P5 (engine/selection.py)
- Status: open
- Text:

  > A candidate of lower authority is selected only when no candidate of higher authority
  > exists for that field. The rule runs over all of a field's candidates.

### R2.47
- Section: Status
- Package: P6
- Status: open
- Text:

  > `status` is now one of three values:

### R2.48
- Section: Status
- Package: P6
- Status: open
- Text:

  > | `known` | The field has candidates, and they all have the same value |

### R2.49
- Section: Status
- Package: P6
- Status: open
- Text:

  > | `contested` | The field's candidates carry two or more different values |

### R2.50
- Section: Status
- Package: P6
- Status: open
- Text:

  > | `unknown` | The field has no candidate; `value` is null |

### R2.51
- Section: Status
- Package: P6
- Status: open
- Text:

  > A `contested` field still has a selected `value` and its citations.

### R2.52
- Section: Status
- Package: P6
- Status: open
- Text:

  > `GET /dossiers` (§8) is unchanged. The `legal_name` it lists is the selected value.

### R2.53
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > The following screens must be reachable by URL. Other screens must be reachable through the UI.
  > Server-side and client-side rendering are both permitted.

### R2.54
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/` | The dossier list with search, and a form to research a domain |

### R2.55
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/dossiers/{domain}` | One dossier: its state, its six fields with their values, status and citations, a refresh and a reload |

### R2.56
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/dossiers/{domain}/evidence` | Every candidate of every field of that dossier |

### R2.57
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/contested` | Every contested field across all dossiers |

### R2.58
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/signup` | Signup |

### R2.59
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > | `/login` | Login |

### R2.60
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > The browser and the API share `/dossiers/{domain}`. Return the UI for `Accept: text/html`;
  > API requests without that header receive JSON. `/`, `/dossiers/{domain}/evidence` and
  > `/contested` are browser routes; they read the API's dossier data. The domain in a browser
  > route is normalised as in §4.

### R2.61
- Section: Screens
- Package: P7a
- Status: open
- Text:

  > The UI must expose the `data-testid` attributes listed below for integration testing. Additional
  > elements are permitted, and the visual implementation is the team's choice subject to the
  > product-quality requirements below.

### R2.62
- Section: Product and visual direction
- Package: P7a/P7b
- Status: open
- Text:

  > The browser experience must feel like a coherent, presentation-ready research product, not a
  > thin wrapper of raw controls. Aim for a calm, legible, evidence-first character: a reader
  > opening a dossier should see at a glance which fields are known, which are unknown and which
  > are contested, and where each value came from.

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

### R2.65
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `signup-email`, `signup-password`, `signup-display-name` | Inputs |

### R2.66
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `signup-submit` | Button |

### R2.67
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `login-email`, `login-password`, `login-submit` | Inputs and button |

### R2.68
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `auth-error` | Error message. Present only when there is one |

### R2.69
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `current-user` | Visible on every screen when signed in. Text contains the display name |

### R2.70
- Section: Signup and login
- Package: P7a
- Status: open
- Text:

  > | `logout-button` | Button |

### R2.71
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `research-domain` | Input for the domain to research |

### R2.72
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `research-submit` | Button. Sends `POST /dossiers` |

### R2.73
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `research-error` | Error message, when the request is refused — including an invalid domain |

### R2.74
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `research-uncertain` | Shown when the outcome of a research request is unknown (below) |

### R2.75
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `dossier-search` | Input. Filters the list as `q` does on `GET /dossiers` |

### R2.76
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `dossier-list` | Container. Children ordered by domain ascending |

### R2.77
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `dossier-item-{domain}` | One per listed dossier. Carries `data-state="{state}"`. Text contains the domain, and the legal name when known. Links to `/dossiers/{domain}` |

### R2.78
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > | `empty-dossiers` | Shown instead of the list when no dossier matches |

### R2.79
- Section: Dossier list — `/`
- Package: P7a
- Status: open
- Text:

  > A research request that succeeds, with 202 or 200, opens `/dossiers/{domain}` for the
  > normalised domain. A domain that already has a dossier, including one created by another
  > client after this browser read the list, opens that dossier and starts no build.

### R2.80
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-domain` | Text is exactly the normalised domain |

### R2.81
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-state` | Text is exactly `building`, `ready` or `failed` |

### R2.82
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-spent` | Formatted `spent_units`. Carries `data-units="{integer}"` |

### R2.83
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-researched-at` | Text contains `researched_at`, formatted. Absent when it is null |

### R2.84
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `field-{field}` | One per field, six in all, in the order of the table in `stage-1.md` §4. Carries `data-status="{status}"` |

### R2.85
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `field-value-{field}` | The formatted value. Carries `data-value` (below). Present only when the value is not null |

### R2.86
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `field-contested-{field}` | A marker. Present only when the field is `contested` |

### R2.87
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `field-citations-{field}` | Container of the field's citations, in API order |

### R2.88
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `citation-{field}-{n}` | The field's `n`th citation, counting from 1. Text contains the excerpt. Contains a link whose `href` is the citation's `url`. Carries `data-provider="{provider}"` |

### R2.89
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-evidence-link` | Link to `/dossiers/{domain}/evidence` |

### R2.90
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-refresh` | Button. Sends `POST /dossiers/{domain}/refresh` |

### R2.91
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `refresh-error` | Error message, when a refresh is refused |

### R2.92
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `refresh-uncertain` | Shown when the outcome of a refresh is unknown (below) |

### R2.93
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-reload` | Button. Reads the dossier again without starting a build |

### R2.94
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > | `dossier-not-found` | Shown instead of the fields when no dossier exists for the domain |

### R2.95
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > `data-value` is the API value as text: a string value unchanged, an integer in plain decimal
  > digits.

### R2.96
- Section: Dossier — `/dossiers/{domain}`
- Package: P7a
- Status: open
- Text:

  > While the dossier's state is `building`, the screen reads the dossier again at least every
  > 2 seconds until the state is `ready` or `failed`, and then shows the new fields without a
  > manual reload.

### R2.97
- Section: Evidence — `/dossiers/{domain}/evidence`
- Package: P7b
- Status: open
- Text:

  > | `evidence-{field}` | One container per field, six in all. Children in API `candidates` order |

### R2.98
- Section: Evidence — `/dossiers/{domain}/evidence`
- Package: P7b
- Status: open
- Text:

  > | `candidate-{field}-{n}` | The field's `n`th candidate, counting from 1. Text contains the formatted value and the excerpt. Carries `data-value`, `data-provider`, `data-kind`, `data-url`, `data-published-at` (the RFC 3339 `published_at`, empty when null) and `data-selected="true"` or `"false"` |

### R2.99
- Section: Evidence — `/dossiers/{domain}/evidence`
- Package: P7b
- Status: open
- Text:

  > | `evidence-empty-{field}` | Shown instead of candidates when the field has none |

### R2.100
- Section: Contested fields — `/contested`
- Package: P7b
- Status: open
- Text:

  > | `contested-list` | Container. Children ordered by domain ascending, then by field in the order of the table in `stage-1.md` §4 |

### R2.101
- Section: Contested fields — `/contested`
- Package: P7b
- Status: open
- Text:

  > | `contested-item-{domain}-{field}` | One per contested field of any dossier. Carries `data-value` for the selected value. Text contains the domain, the field and every distinct candidate value. Links to `/dossiers/{domain}/evidence` |

### R2.102
- Section: Contested fields — `/contested`
- Package: P7b
- Status: open
- Text:

  > | `empty-contested` | Shown instead of the list when no field is contested |

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

### R2.104
- Section: Refresh and competing clients
- Package: P7a
- Status: open
- Text:

  > - `dossier-reload` reads the dossier again. **Latest read wins:** a delayed earlier read must
  >   not overwrite a later one, including when responses arrive out of order. This applies to the
  >   reads while a dossier is `building` as well.

### R2.105
- Section: Refresh and competing clients
- Package: P7a
- Status: open
- Text:

  > - Another client may refresh a dossier after this browser reads it. A refresh from this
  >   browser while that build runs is answered 202 like any other and the screen follows the
  >   running build to its end.

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

### R2.107
- Section: Refresh and competing clients
- Package: P7a
- Status: open
- Text:

  > No background polling beyond the reading while `building`, live synchronization, or recovery
  > across page reloads is required.

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

### R2.109
- Section: Existing clients after an upgrade
- Package: P6
- Status: open
- Text:

  > The candidates of an imported dossier are replaced by those of its next completed build.
