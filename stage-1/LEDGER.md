# Dossier — Requirements Ledger (cumulative; stage 1 section)

Statuses: open → built → tested → accepted. Source: challenges/dossier/spec/stage-1.md.
Packages: WP1 platform (builder-a) · WP2 support engine, Appendix A (builder-b) · WP3 research/build engine (builder-b) ·
WP4 dossier API, idempotency, lifecycle, export/import (builder-a) · TEST prover (cross-cutting tests) · GK gatekeeper (checks/cost measures).

Interface between WP3 and WP4 (ruling G1): package `research` exposes a synchronous, never-raising
`run_build(domain: str) -> BuildOutcome` where `BuildOutcome = {ok: bool, fields: {six field names -> {"value", "citations":[{url, excerpt, provider}]}}, spent_units: int}`;
`ok=false` means state `failed` (no provider call succeeded); the service runs it on a worker thread and applies the result only if the dossier's generation is unchanged (reset/import bumps it).
Interface between WP2 and WP3: pure module `support` — `supports(excerpt, domain) -> list[(field, value)]` (all (field, normalised value) pairs the single excerpt supports), `split_sentences(text)`, `page_prose(text)`, `candidate_excerpts(text)`.

## Rulings
- **G1** Interface above. Language: Python 3.12, whole service in one process, `web_router` called in-process. State in memory behind one lock; export = JSON dump of that state.
- **G2** Nimble alone is used for research (Tavily never called): Tavily's costs are higher and Nimble alone is mandated sufficient (§2).
- **G3** Idempotency record is keyed by (user, method, normalised-by-nothing raw path, key). Same key on a different path is an independent request. Same key, same path, different JSON body (comparing only the known field `domain`, raw as written, case-sensitive) → 409. Only successful (2xx) responses are stored; 4xx leave the key unclaimed. A replay always answers 200 with the original body. Concurrent identical requests: per-(user,key) in-flight lock, one executes, the rest wait and return 200 with the same body.
- **G4** Request order of checks: route → bearer auth (401) → `Idempotency-Key` missing/empty (400) → body parse (400) → key length >255 (422) → already-claimed key resolution (200 replay / 409) → field validation (422) → execute. (The spec says the claimed-key resolution precedes field validation, only after the body parsed as a JSON object and the caller is authenticated.)
- **G5** `POST /dossiers` body must be a JSON object, else 400 `malformed_request`; `domain` wrong JSON type → 400; missing/null → 422; invalid after normalisation → 422. `POST .../refresh` ignores any body (even unparseable).
- **G6** Emails are case-insensitive for uniqueness and login (lowercase on store/lookup); `local@domain` = exactly one `@`, non-empty both sides, no whitespace. `display_name` empty/whitespace-only/>100 chars → 422. Wrong JSON type → 400. Validate (422) before checking `email_taken` (409). Password length counted in characters.
- **G7** A build that makes ≥1 successful provider call ends `ready` even if every field is unknown; `failed` only if no provider call succeeded. Provider error status costs 0; timeout/connection failure costs the table price (counted by our own accounting, not the mock's log).
- **G8** After import, a dossier whose export showed a build in progress is shown in the state of its last completed build; export records dossiers as before the running build and `failed` + all-unknown when none completed. `researched_at` stays that of the last ready build.
- **G9** Domain in `idempotency` body comparison is raw (`Acme-Robotics.test` ≠ `acme-robotics.test`), but the dossier is the same.
- **G10** Unknown routes 404 `not_found`; wrong method 405 `method_not_allowed`; all error bodies use §5 shape. No 5xx for any input.
- **G11** Evidence completeness drives correctness: a build must find every page the mock returns for any query naming the company (not only the page set from the one query), plus research-cited pages (possibly non-searchable → fetch by Nimble extract), and decide each field `known` iff some excerpt in the gathered text supports a value (Appendix A applied by the service). Facts headers are never a source. Budget 80 units hard cap (own accounting before each call).
- **G12** Live-provider timing (§8): per-call timeout ≥ 30 s (use 60 s), overall build deadline 280 s; with the mock (calls <1 s) a build must finish < 10 s, so issue independent calls in parallel.

## Ledger (stage 1)

| id | § | owner | status | verbatim text |
|---|---|---|---|---|
| R1.1 | 1 | WP4 | open | A caller asks for a company by its web domain. |
| R1.2 | 1 | WP3 | open | Every value the service asserts cites at least one excerpt that a provider endpoint served to this service, and that excerpt supports the value. No citation is invented, reworded, or attached to a value it does not support. |
| R1.3 | 1 | WP3 | open | No build of a dossier spends more than 80 units (§9). |
| R1.4 | 1 | WP4 | open | A dossier is built in the background, read any number of times, and refreshed on request. Only the HTTP API is required. |
| R1.5 | 1 | WP4 | open | The following apply to all operations, including concurrent requests and retries: |
| R1.6 | 1 | WP4 | open | Contact data, people search, and fields other than the six in §4 are out of scope. |
| R1.7 | intro | all | open | Build from the supplied requirements. Source code, API documentation and schemas from existing products in this domain must not be used. WebRouter's own documentation may be used. |
| R1.8 | 2 | WP1 | open | Deliver an HTTP service, a `Dockerfile` and a `RUN.md` with a command that builds and starts the service without manual setup. |
| R1.9 | 2 | WP1 | open | The image must run on its own with `-e PORT=<port>` and a port mapping. All runtime dependencies, initialization and seed data must work within that single container. Compose configuration is not used to start the service. |
| R1.10 | 2 | WP1 | open | The submitted `Dockerfile` is built and started, and only its HTTP behavior is exercised |
| R1.11 | 2 | WP3 | open | Nimble is the default provider: every service must be able to research companies using Nimble alone. Tavily is optional: a service may use it beside Nimble, and its absence must not prevent research while Nimble answers. |
| R1.12 | 2 | WP3 | open | The service reaches the providers only through WebRouter, the Python package `webrouter` (module `web_router`). ... every request to a provider goes through `web_router`: called in-process, or from a Python helper process that the service runs inside its own container. |
| R1.13 | 2 | WP1 | open | The stage folder's dependency manifest lists `webrouter>=0.12.0`. Calling a provider's API by any other route is not permitted. Install it and the provider SDK dependencies from PyPI, including in the service's Docker build: `pip install "webrouter[search,extract,research]>=0.12.0"` |
| R1.14 | 2 | WP3 | open | A service that uses Tavily passes its base URL to WebRouter in `provider_config`: `provider_config={"tavily": {"api_base_url": <TAVILY_BASE_URL>}}` (WebRouter's `nimble` provider reads `NIMBLE_API_KEY` and `NIMBLE_BASE_URL` from the environment) |
| R1.15 | 2 | WP1 | open | Resource limits: CPU 2 vCPU; Memory 3 GiB; Start to first healthy response 60 s; Concurrent requests up to 50 in flight; Per-request timeout 5 s (10 s for `POST /_test/reset`) |
| R1.16 | 2 | WP1 | open | Outbound network: available during `docker build`; at run time, **only the provider endpoints this specification lists** |
| R1.17 | 2 | WP1 | open | Runtime assets and dependencies must be included in the image. |
| R1.18 | 3.1 | WP1 | open | Listen on `0.0.0.0` using the `PORT` environment variable, default `8080`. |
| R1.19 | 3.2 | WP1 | open | `GET /health -> 200 {"status": "ok"}` Return 200 once the service and its data store can serve requests, within 60 seconds of container start. |
| R1.20 | 3.2 | WP1 | open | `/health` makes no provider call. |
| R1.21 | 3.3 | WP1 | open | `POST /_test/reset` with body {...fixture...} -> 204 No Content. Replace all service state with the fixture in the request body (§4). |
| R1.22 | 3.3 | WP1 | open | When reset returns 204, subsequent requests must see only that fixture: no users other than the seeded ones, no dossiers and no stored idempotent responses. Repeated resets are supported. |
| R1.23 | 3.3 | WP4 | open | A build still running when reset is called must not change the state that follows the reset. |
| R1.24 | 3.3 | WP1 | open | This control endpoint must be enabled in the delivered image and requires no authentication. |
| R1.25 | 3.4 | WP1 | open | The service keeps a clock that only reset and `POST /_test/clock` move. Every timestamp the service records or returns is read from this clock. |
| R1.26 | 3.4 | WP1 | open | `POST /_test/clock` {"now": "2026-03-01T09:30:00+00:00"} -> 204 No Content |
| R1.27 | 3.4 | WP1 | open | Reset sets the clock to the fixture's `now`. Before the first reset the clock follows the system time. |
| R1.28 | 3.4 | WP1 | open | The clock stands still between calls: two requests with no clock call between them read the same time. |
| R1.29 | 3.4 | WP1 | open | `now` is an RFC 3339 timestamp with an explicit offset. A `now` earlier than the clock's current time is 422 `validation_failed` and changes nothing. |
| R1.30 | 3.4 | WP1 | open | `POST /_test/clock` requires no authentication. |
| R1.31 | 3.5 | WP1 | open | Requests and responses are `application/json; charset=utf-8`. |
| R1.32 | 3.5 | WP1 | open | Timestamps in responses are RFC 3339 with an explicit offset, e.g. `2026-09-24T19:00:00+02:00`. |
| R1.33 | 3.5 | WP1 | open | Unknown fields in a request body are ignored, never an error. |
| R1.34 | 3.5 | WP1 | open | Unknown query parameters are ignored. |
| R1.35 | 3.5 | WP1 | open | IDs are opaque strings of at most 64 characters. Their format is yours. |
| R1.36 | 4 | WP1 | open | Users sign up and log in (§6). Every authenticated user sees the same dossiers. |
| R1.37 | 4 | WP4 | open | Every domain the API takes, in a body or a path, is first **normalised**: surrounding whitespace removed, lowercased, one trailing `.` removed, and one leading `www.` removed. |
| R1.38 | 4 | WP4 | open | The normalised domain must then be a valid host name: two or more labels separated by `.`, each label 1 to 63 characters of `a-z`, `0-9` and `-`, not starting or ending with `-`, and 253 characters or fewer in total. Anything else, including a URL with a scheme or a path, is 422 `validation_failed`. |
| R1.39 | 4 | WP4 | open | `Acme-Robotics.TEST.`, `www.acme-robotics.test` and `acme-robotics.test` name the same company and the same dossier. Responses always carry the normalised domain. |
| R1.40 | 4 | WP4 | open | A dossier has exactly these six fields: `legal_name` (String), `hq_city` (String: the city ... without region or country), `ceo` (String: full name), `founded_year` (Integer), `headcount_range` (String: one of `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+`), `funding_total` (Integer: total equity funding raised, in whole US dollars) |
| R1.41 | 4 | WP2 | open | A string value is written as the supporting excerpt writes it, without surrounding whitespace. A headcount the web states as a number, or as a range that fits inside one of the ranges above, has the range that contains it as its value. |
| R1.42 | 4 | WP4 | open | Each field in a response has this shape: {"value": "Dana Ruiz", "status": "known", "citations": [ {"url": ..., "excerpt": ..., "provider": "nimble"} ]} |
| R1.43 | 4 | WP4 | open | `status` is `known` when `value` is not null, and `unknown` when it is. |
| R1.44 | 4 | WP4 | open | A `known` field has one or more citations. An `unknown` field has `"value": null` and `"citations": []`. |
| R1.45 | 4 | WP3 | open | `url` is the URL of the page the excerpt was served for, `provider` is `nimble` or `tavily`, the provider that served it. |
| R1.46 | 4 | WP3 | open | The **evidence** for a company is every page that some search, through any provider and for any query naming the company (as in Appendix A.2), returns, with its full text, and every claim that a `nimble` research run for the company asking for all six fields answers with. |
| R1.47 | 4 | WP3 | open | Of the searches that a provider answers without an error, every build makes exactly one whose query is exactly the company's normalised domain, through a provider of its choice; its other such searches use other queries. A search that a provider answers with an error does not count. The pages whose text a build obtains from providers are the pages it **gathers**. |
| R1.48 | 4 | WP3 | open | A **citation** is an excerpt of text a provider served for the page at `url`: The excerpt is copied character for character from that served text, except that any run of whitespace may be written as a single space. It is 1 to 500 characters long. |
| R1.49 | 4 | WP3 | open | It is taken from the page's prose (below), not from its header. |
| R1.50 | 4 | WP2 | open | An excerpt **supports** a value when, read on its own, it states that value for that field of this company, as Appendix A defines. The excerpt may write the value differently from the API (`$12M` / `12 million dollars` → 12000000; `employs about 120 people` → `51-200`). |
| R1.51 | 4 | WP3 | open | A research answer carries a claimed value for a field and a citation for the claim. The claim is asserted only when its citation supports it. A field is `unknown` when no evidence supports a value for it, even when a research answer claims one. |
| R1.52 | 4 | WP3 | open | When the evidence supports more than one value for a field, the field holds one of them and cites only excerpts that support that value. |
| R1.53 | 4 | WP2 | open | Every page has a URL, a title and a text. A text may begin with **header lines**, each of the form `Name: value`, where the name is a capitalised word or several joined by `-`. The header ends at the first empty line; everything after it is the page's **prose**. A text whose first line is not a header line has no header and is all prose. |
| R1.54 | 4 | WP2 | open | The header line `Facts:` carries a JSON object on the same line. ... It is informative only: citations come from the prose, and whether an excerpt supports a value is decided by Appendix A alone. The service may ignore other header lines. |
| R1.55 | 4 | WP1 | open | Fixture: `now` is required and sets the clock (§3.4). Seeded users must be able to log in with the given password immediately. |
| R1.56 | 4 | WP1 | open | A fixture with two users sharing an email is a reset error: 422 `validation_failed`, changing nothing. |
| R1.57 | 5 | WP1 | open | Every 4xx and 5xx response carries this body: { "error": { "code": "not_found", "message": "human readable, any wording" } } |
| R1.58 | 5 | WP1 | open | 400 `malformed_request`: Unparseable body, or a field of the wrong JSON type |
| R1.59 | 5 | WP4 | open | 400 `missing_idempotency_key`: Required `Idempotency-Key` header absent or empty |
| R1.60 | 5 | WP1 | open | 401 `unauthenticated`: Missing, malformed or unknown bearer token |
| R1.61 | 5 | WP4 | open | 404 `not_found`: No such resource, or not visible to this caller |
| R1.62 | 5 | WP4 | open | 409 `idempotency_key_reuse`: Key already used by this caller with a different request body |
| R1.63 | 5 | WP1 | open | 422 `validation_failed`: A required field or query parameter is missing, or a stated rule is violated with no more specific code |
| R1.64 | 5 | WP1 | open | A field of the correct JSON type with an invalid format or out-of-range value gives 422 `validation_failed`, unless an endpoint specifies a different error. |
| R1.65 | 5 | WP4 | open | An integer-valued **query parameter** is written as plain decimal digits: `1e9`, `4.0` and `+4` are 422 `validation_failed` whatever their numeric value. |
| R1.66 | 5 | WP1 | open | Reserve 400 `malformed_request` for a body that does not parse or a field of the wrong type. |
| R1.67 | 5 | WP4 | open | Shared ranges: `Idempotency-Key` 1 to 255 characters (else 422 `validation_failed`); `limit` integer 1 to 200 (else 422); `offset` integer 0 or more (else 422) |
| R1.68 | 5 | all | open | Requests must not produce 5xx responses, including under concurrent load and when a provider endpoint answers with an error. |
| R1.69 | 6 | WP1 | open | `POST /auth/signup` {email,password,display_name} -> 201 { "user_id": "u_1", "display_name": "Ada", "token": "..." } |
| R1.70 | 6 | WP1 | open | `POST /auth/login` {email,password} -> 200 { "user_id": "u_1", "display_name": "Ada", "token": "..." } |
| R1.71 | 6 | WP1 | open | Email already registered: 409 `email_taken`. Password shorter than 8 characters: 422 `validation_failed`. `email` not of the form `local@domain`: 422. `display_name` empty or longer than 100 characters: 422. Wrong password or unknown email on login: 401 `unauthenticated` |
| R1.72 | 6 | WP1 | open | For a user seeded by the fixture (§3.3), `user_id` is that user's `id` in the fixture. |
| R1.73 | 6 | WP1 | open | Every other endpoint requires a bearer token, except `/health`, the `/_test/*` endpoints and the two above. A request to such an endpoint that lacks a valid token is 401 `unauthenticated`, even when it also lacks a required `Idempotency-Key`. |
| R1.74 | 6 | WP1 | open | Tokens do not expire. An account may have multiple valid tokens and concurrent sessions. |
| R1.75 | 6 | WP1 | open | Passwords must be stored using a password-hashing function such as bcrypt, scrypt or Argon2, or an equivalent. Plaintext password storage is not permitted. |
| R1.76 | 7 | WP4 | open | Two write paths require an idempotency key (§8): **`POST /dossiers`** and **`POST /dossiers/{domain}/refresh`**. Everything below applies to each of them independently. |
| R1.77 | 7 | WP4 | open | The key is scoped to **the authenticated user**. Two different users may use the same key string with no interaction between them. |
| R1.78 | 7 | WP4 | open | A replay means the same user sending the **same method, the same path and the same body**. The same key with the same body on a different path is a different request, not a replay, and must succeed normally. `Acme-Robotics.test` and `acme-robotics.test` in a path or body are different requests for this rule, though they name the same dossier. |
| R1.79 | 7 | WP4 | open | Header absent or empty → 400 `missing_idempotency_key`; First use → the normal response (§8); Replay: same key, same body → **200**, body identical to the original response as a JSON value; Same key, different body → 409 `idempotency_key_reuse`; Key reused after the original request failed with 4xx → Treated as a first use |
| R1.80 | 7 | WP4 | open | "Same body" means the same JSON value after parsing — key order and whitespace do not matter. Unknown fields are ignored (§3.5) and play no part in this comparison: a body that differs from the first only in unknown fields is the same body, so the request is a replay. `POST /dossiers/{domain}/refresh` takes no body; any body sent to it is ignored and plays no part in deciding a replay. |
| R1.81 | 7 | WP4 | open | For concurrent identical requests with an unused key, exactly one returns the normal response. The others return 200 with the same body. The operation takes effect only once. |
| R1.82 | 7 | WP4 | open | A successful replay returns the original response, even after the dossier has changed. It starts no build and makes no provider call. |
| R1.83 | 7 | WP4 | open | After the body has parsed as a JSON object and the caller is authenticated, an already claimed key is resolved before field validation. Thus changing a successful request to an invalid body with the same key still returns `409 idempotency_key_reuse`. |
| R1.84 | 8 | WP4 | open | A **build** researches one dossier: it calls the providers, decides each field, and replaces the dossier's fields with the result when it completes. A dossier's first build starts with `POST /dossiers`, and every later one with `POST /dossiers/{domain}/refresh`. A build's **time** is the clock's time when the request that started it was received. |
| R1.85 | 8 | WP4 | open | A dossier has at most one build running at a time. |
| R1.86 | 8 | WP4 | open | A build ends in `ready` when it completed, or `failed` when none of its provider calls succeeded. A failed build leaves the fields as they were. |
| R1.87 | 8 | WP3 | open | When a build completes `ready`, each field is `known` exactly when the evidence (§4) supports a value for it. |
| R1.88 | 8 | WP3 | open | A build whose provider calls each answer within one second ends within 10 seconds of the request that started it. |
| R1.89 | 8 | WP3 | open | Against the live providers (`NIMBLE_BASE_URL` unset, or its host `sdk.nimbleway.com`), where a Nimble search can take over ten seconds and a research run about a minute, a build does not give up on a call that has been waiting less than 30 seconds, nor stop gathering because of the time it has run in its first 120 seconds. It still ends `ready` or `failed` within 300 seconds. |
| R1.90 | 8 | WP4 | open | Reading a dossier, listing dossiers and every other request except `POST /dossiers` and `POST /dossiers/{domain}/refresh` make no provider call. |
| R1.91 | 8 | WP4 | open | `POST /dossiers` Idempotency-Key required; body {"domain": ...} → 202 { "dossier_id": "d_7", "domain": "acme-robotics.test", "state": "building" } |
| R1.92 | 8 | WP4 | open | When no dossier exists for the domain, the service creates one, starts its first build and returns 202. When a dossier already exists for the domain, the service starts no build and returns **200** with that dossier's `dossier_id`, `domain` and current `state`. |
| R1.93 | 8 | WP4 | open | Concurrent requests for the same domain create one dossier and start one build, whatever their keys. |
| R1.94 | 8 | WP4 | open | `POST /dossiers`: `domain` missing → 422 `validation_failed`; `domain` invalid after normalisation (§4) → 422 `validation_failed` |
| R1.95 | 8 | WP4 | open | `GET /dossiers/{domain}` returns {dossier_id, domain, state, researched_at, spent_units, fields{six}} |
| R1.96 | 8 | WP4 | open | `state` is `building` while a build runs, otherwise the outcome of the latest build, `ready` or `failed`. |
| R1.97 | 8 | WP4 | open | `fields` always holds all six fields. Before the first build completes `ready`, every field is `unknown`. While a later build runs, `fields` are those of the last build that completed `ready`. |
| R1.98 | 8 | WP4 | open | `researched_at` is the time of the last build that completed `ready`, or null. |
| R1.99 | 8 | WP4 | open | `spent_units` is the total cost (§9) of every provider call made for this dossier, by every build, since it was created. |
| R1.100 | 8 | WP4 | open | The domain in the path is normalised (§4). No dossier for it is 404 `not_found`. |
| R1.101 | 8 | WP4 | open | `POST /dossiers/{domain}/refresh`: Idempotency-Key required. No body. Starts a new build of the dossier and returns 202 with `{ "dossier_id", "domain", "state": "building" }`. A refresh received while a build of the dossier is running starts no second build and returns 202 with the same body. |
| R1.102 | 8 | WP3 | open | A refresh researches again: its build makes provider calls whether or not anything has changed since the last build, and its spending counts in `spent_units`. |
| R1.103 | 8 | WP4 | open | Refresh: No dossier for the domain → 404 `not_found` |
| R1.104 | 8 | WP4 | open | `GET /dossiers?q=acme&limit=50&offset=0` → { "dossiers": [ {dossier_id, domain, state, legal_name, researched_at, spent_units} ], "has_more": false } |
| R1.105 | 8 | WP4 | open | `legal_name` is the value of the dossier's `legal_name` field, or null. |
| R1.106 | 8 | WP4 | open | `q` is optional. When present, only dossiers whose domain or `legal_name` contains `q`, compared case-insensitively, are listed. An empty `q` lists every dossier. |
| R1.107 | 8 | WP4 | open | Dossiers are ordered by domain ascending. |
| R1.108 | 8 | WP4 | open | `limit` defaults to 50, range 1 to 200. `offset` defaults to 0. `has_more` is true when items exist beyond the last one returned. |
| R1.109 | 9 | WP3 | open | Cost in units: Search nimble lite 1 / fast 5 / deep 15; Search tavily lite 8 / fast 16 / deep 16; Extract nimble 1 per URL requested, including a URL for which no page is returned; Extract tavily 2 per URL; Research run through `nimble` 25 when the run is started; checking on or collecting a run costs nothing. A search's depth is WebRouter's `search_depth`. |
| R1.110 | 9 | WP3 | open | A search returns at most 10 results, whatever number it asks for. A call that a provider refuses with an error status costs nothing. A call whose answer does not arrive, because it times out or its connection fails, costs its units as in the table, whether or not the provider received it. An extract that the provider answers with no page for the URL is not refused: it costs its units, as in the table, whatever status says so. An extract through `nimble` does not set `render`. |
| R1.111 | 9 | WP3 | open | A build stops making provider calls before its spending would exceed 80 units, and completes with the pages and research claims it has obtained. |
| R1.112 | 9 | WP3 | open | A research request names the company by its domain in its query, and names the fields it asks for by the field names in §4, as the property names of its output schema. |
| R1.113 | 10 | WP4 | open | The service must support `GET /_test/export` and `POST /_test/import`. Like reset, these are unauthenticated control endpoints. Exports may contain credentials and session tokens; handle them as private artifacts. |
| R1.114 | 10 | WP4 | open | Return 200 from export with a JSON object containing `track: "dossier"`, `format_version: 1` and `state` (an implementation-defined JSON object). The state format is opaque to the caller and must be accepted unchanged by import. |
| R1.115 | 10 | WP4 | open | Import takes that entire object and atomically replaces the service's state, returning 204. It must accept an unchanged export produced by this service. No dependency on the source process, files, volume, port or network address is allowed. Import is replacement, not merge; repeating it restores the exported state without duplicating anything. |
| R1.116 | 10 | WP4 | open | Invalid JSON follows §5; missing fields, wrong track/version or an invalid state give 422 `validation_failed` without changing the destination. These control calls have a 10-second timeout. Export is an atomic, read-only snapshot; subsequent source writes do not change it. |
| R1.117 | 10 | WP4 | open | Preserve accounts and hashed-password login, existing bearer tokens, dossiers with their ids, states, fields, citations, `researched_at` and `spent_units`, all completed idempotent request bodies and original responses. Identities and timestamps must not be regenerated. |
| R1.118 | 10 | WP4 | open | Import makes no provider call: imported dossiers are not researched again, and their citations remain citations served to this service. Failed request keys remain reusable. Existing tokens and retries must remain valid after import; replacing the state with a fresh fixture does not satisfy this requirement. Import removes all previous destination data and credentials. Reset clears all state, including imported state. Export and import do not change the clock. State need not survive an abrupt container restart. |
| R1.119 | 10 | WP4 | open | An export taken while a build is running holds the dossier as it was before that build; after import, that dossier is in the state of its last completed build, or `failed` with every field `unknown` when no build had completed. |
| R1.120 | 11 | WP4 | open | Concurrent requests must produce the same results as executing them one at a time in some order. The requirements above hold at every read. |
| R1.121 | A.1 | WP2 | open | A page's prose is split into lines at each line break, and each line into sentences. A sentence ends after a `.`, `!` or `?`, together with any `"`, `”`, `’` or `)` directly after it, when whitespace follows. A `.` that ends one of the legal-form suffixes in A.4, written as a whole word, does not end a sentence. Each sentence is taken without its surrounding whitespace; empty sentences are dropped. |
| R1.122 | A.1 | WP2 | open | An excerpt is a **single sentence** when, with every run of whitespace written as one space, this rule splits it into exactly one sentence. |
| R1.123 | A.2 | WP2 | open | An excerpt supports the value V for the field F of a company exactly when all of these hold: 1. It is a single sentence (A.1). 2. It names the company: it contains the company's normalised domain, or the company's name. The company's name is the first label of its domain with each `-` read as a space: `acme-robotics.test` is named by `Acme Robotics`. 3. It contains a statement phrase for F (A.3). 4. It contains none of the negating phrases (A.3). 5. It contains at least one value in F's format (A.4), and every value in F's format that it contains normalises to V (A.5). |
| R1.124 | A.2 | WP2 | open | The company's name, its domain and every phrase are matched without regard to case and as whole words: the characters directly before and after the match are not letters or digits. Phrases with a space match one space. |
| R1.125 | A.2 | WP2 | open | Examples: `Dana Ruiz has led Acme Robotics as chief executive since 2021.` → ceo Dana Ruiz; `Acme Robotics CEO: Sam Ortiz.` → ceo Sam Ortiz; `Acme Robotics was founded in 2014.` → founded_year 2014; `Acme Robotics employs about 120 people.` → headcount_range 51-200; `Acme Robotics is reportedly in talks to raise $40M.` → nothing (negating phrase); `Acme Robotics opened a sales office in Porto.` → nothing (no statement phrase for hq_city) |
| R1.126 | A.3 | WP2 | open | Statement phrases — legal_name: `legal name`, `registered name`, `registered as`, `registered company`, `legal entity`, `name of record`; hq_city: `headquartered in`, `headquarters in`, `head office in`, `based in`, `registered office in`, `registered seat in`; ceo: `chief executive officer`, `chief executive`, `CEO`; founded_year: `founded`, `founding`, `established`, `incorporated`; headcount_range: `employs`, `employees`, `staff`, `people`, `headcount`, `workforce`; funding_total: `raised`, `funding`, `invested`, `investment` |
| R1.127 | A.3 | WP2 | open | The negating phrases are: `in talks to`, `plans to`, `planning to`, `wants to`, `expects to`, `hopes to`, `aims to`, `seeking`, `could`, `would`, `might`, `reportedly`, `rumoured`, `former`, `formerly`, `will become`, `not`. |
| R1.128 | A.4 | WP2 | open | A **capitalised word** is an uppercase letter followed by one or more lowercase letters, with no letter or digit directly before or after it. The letters may be of any alphabet: `Zürich` and `Müller` are capitalised words. An **uppercase word** is two or more uppercase letters, with no letter or digit directly before or after it: `AI`, `USA`. |
| R1.129 | A.4 | WP2 | open | A **number** is written in digits, optionally with a `,` before each group of three digits and a decimal part after a `.`: `120`, `1,200`, `12.5`, `12,000,000`. Digits directly next to a letter, or joined to other digits by `,` or `.` in any other way, are not a number. |
| R1.130 | A.4 | WP2 | open | legal_name format: The company's name or its domain (matched as in A.2), then zero or more capitalised or uppercase words each after one space, then an optional `,`, one space, and a legal-form suffix with no letter or digit directly after it. Where several such texts start at the same place, the shortest counts |
| R1.131 | A.4 | WP2 | open | hq_city format: A place name directly after a statement phrase for `hq_city` and one space: the longest run of capitalised words joined by single spaces or by `-` that starts there, not part of a longer such run |
| R1.132 | A.4 | WP2 | open | ceo format: A person's name: a run of two or three capitalised words joined by single spaces that is not part of a longer such run. Occurrences of the company's name and of the statement phrases for `ceo` are first taken out of the sentence and separate the words around them |
| R1.133 | A.4 | WP2 | open | founded_year format: A number of exactly four digits, from 1800 to 2099, that is not part of an amount |
| R1.134 | A.4 | WP2 | open | headcount_range format: A number with no decimal part, 1 or more, that is not part of an amount. Words before it, such as `about` or `roughly`, do not change it. A stated range such as `51-200 employees` holds two numbers |
| R1.135 | A.4 | WP2 | open | funding_total format: An amount (below) |
| R1.136 | A.4 | WP2 | open | The legal-form suffixes, matched exactly as written here: `Inc.`, `Corp.`, `LLC`, `LLP`, `L.P.`, `Ltd`, `Limited`, `Pty Ltd`, `plc`, `PLC`, `GmbH`, `AG`, `KG`, `SE`, `AS`, `A/S`, `ASA`, `AB`, `Oy`, `Oyj`, `B.V.`, `N.V.`, `S.A.`, `S.A.S.`, `S.L.`, `S.r.l.`, `S.p.A.`, `s.r.o.`, `a.s.`, `K.K.`. |
| R1.137 | A.4 | WP2 | open | An **amount** is written in one of these forms, matched without regard to case, with no letter or digit directly before it or after it: `$`, `US$` or `USD`, an optional space, a number, and optionally a scale: `k`, `m`, `mn` or `bn` directly after the number, or one space and `thousand`, `million` or `billion` (e.g. `$12M`, `$12.5 million`, `US$12 million`, `USD 12 million`, `$12m`, `$12,000,000`); or a number, optionally one space and `thousand`, `million` or `billion`, then one space and `dollars` or `US dollars` (e.g. `12 million dollars`, `12,000,000 US dollars`). Amounts in other currencies are not amounts. |
| R1.138 | A.5 | WP2 | open | Normalisation: `legal_name`, `hq_city`, `ceo`: the text as the excerpt writes it; `founded_year`: the number as an integer; `headcount_range`: the range of §4 that contains the number; `funding_total`: the number times the scale (`k` and `thousand` 1,000; `m`, `mn` and `million` 1,000,000; `bn` and `billion` 1,000,000,000) in US dollars. An amount that does not come to a whole number of dollars is not a value |
| R1.139 | cost | GK | open | MEASURE: `spent_units` per build ≤ 80 on every revision (compare dossier `spent_units` and the mock `GET /_mock/log` costs, which must agree) |
| R1.140 | timing | GK | open | MEASURE: build wall time < 10 s with the mock (calls <1 s); per-request latency < 5 s with 50 in flight; start to healthy < 60 s |

## Frozen revision
(not frozen)

## In-flight list
(see lead messages)
