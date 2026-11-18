# Requirements ledger — Dossier

Owner: `@lead`. Cumulative across stages. Statuses: `open` → `built` → `tested` → `accepted`.
Source for stage 1: `challenges/dossier/spec/stage-1.md` (quoted verbatim below).

Stage 1 opened: 2026-11-18T19:32Z. Frozen revision: _not yet frozen_.

## Packages (stage 1)

| Package | Owner | Area (disjoint) | Order | Ledger ids |
|---|---|---|---|---|
| P1 Skeleton, runtime contract, auth | `@builder-a` | `stage-1/Dockerfile`, `stage-1/RUN.md`, `stage-1/requirements.txt`, `stage-1/app/` except `stage-1/app/research/`, `stage-1/tests/api/` | 1 (first deliverable that builds and starts) | R1.03–R1.17, R1.18–R1.33, R1.34–R1.41, R1.47–R1.50 |
| P2 Dossier API, idempotency, builds orchestration, export/import, concurrency | `@builder-a` | same area as P1 | 2 | R1.01, R1.42–R1.46, R1.51–R1.62, R1.66–R1.69, R1.70–R1.92, R1.106–R1.120 |
| P3 Support engine (Appendix A, pages, citations) | `@builder-b` | `stage-1/app/research/support.py`, `stage-1/app/research/pages.py`, `stage-1/tests/research/` | 1 | R1.63–R1.65, R1.95–R1.97, R1.121–R1.140 |
| P4 Research engine (WebRouter, gathering, budget, evidence, timing) | `@builder-b` | `stage-1/app/research/` (rest), `stage-1/tests/research/` | 2 | R1.02, R1.09–R1.12, R1.93–R1.94, R1.98–R1.105, R1.141–R1.153 |
| P5 Limits and robustness under load (latency, concurrency, event-loop isolation of builds, reset under load) | `@builder-a` | `stage-1/app/` except `stage-1/app/research/`, `stage-1/tests/api/`, `stage-1/tests/load/` | 3 | R1.12, R1.15, R1.23, R1.58, R1.76, R1.88, R1.120a |
| PT Acceptance suite | `@prover` | `acceptance/stage-1/` at repo root | parallel | all |
| Review, checks, merge | `@gatekeeper` | integration branch `main` | continuous | all |

The owner tag on each entry below is authoritative; the id ranges in this table are a summary. Interface between P2 and P4: ruling L1.01.

## Measures (tracked on every revision)

| Id | Measure | Target | How measured |
|---|---|---|---|
| M1.1 | Units spent per build | ≤ 80 (R1.02, R1.148) | Mock `GET /_mock/log` cost per build window, and `spent_units` delta per build; Gatekeeper reports the per-build max and mean over the sample corpus vs the previous accepted revision |
| M1.2 | Build wall time with ≤1 s provider answers | ≤ 10 s (R1.100) | Prover timing test; mock `delay` fault at 1 s |
| M1.3 | Start to first healthy `/health` | ≤ 60 s (R1.13, R1.20) | Gatekeeper, under `--cpus 2 --memory 3g` |
| M1.4 | Per-request latency | < 5 s (10 s reset) (R1.15) | Prover, incl. 50 concurrent requests |
| M1.5 | Field accuracy | every field equal to the corpus key's expected value | Event check `test_build_a_dossier` and Prover corpus sweep |

## Requirements

### §0 Preamble
- **R1.00** §0 — P1 — built
  > Build from the supplied requirements. Source code, API documentation and schemas from existing products in this domain must not be used. WebRouter's own documentation may be used.

### §1 Scope
- **R1.01** §1 — P2/P4 — built
  > A caller asks for a company by its web domain. The service researches the company on the web and keeps a **dossier**: a profile of six fields, each with the value the web supports and the excerpts it came from. A dossier is built in the background, read any number of times, and refreshed on request. Only the HTTP API is required.
- **R1.01a** §1.1 — P3/P4 — built
  > Every value the service asserts cites at least one excerpt that a provider endpoint served to this service, and that excerpt supports the value. No citation is invented, reworded, or attached to a value it does not support.
- **R1.02** §1.2 — P4 — built (measure M1.1)
  > No build of a dossier spends more than 80 units (§9).
- **R1.02a** §1 — P4 — built
  > Contact data, people search, and fields other than the six in §4 are out of scope.

### §2 Delivery and deployment
- **R1.03** §2 — P1 — built
  > Deliver an HTTP service, a `Dockerfile` and a `RUN.md` with a command that builds and starts the service without manual setup.
- **R1.04** §2 — P1 — built
  > The submitted `Dockerfile` is built and started, and only its HTTP behavior is exercised; it does not import or execute the submission's source files on the host that runs it.
- **R1.05** §2 — P1 — built
  > The image must run on its own with `-e PORT=<port>` and a port mapping. All runtime dependencies, initialization and seed data must work within that single container. Compose configuration is not used to start the service.
- **R1.06** §2 Web access — P4 — built
  > Nimble is the default provider: every service must be able to research companies using Nimble alone. Tavily is optional: a service may use it beside Nimble, and its absence must not prevent research while Nimble answers.
- **R1.07** §2 Web access — P4 — built
  > The service reaches the providers only through WebRouter, the Python package `webrouter` (module `web_router`). ... every request to a provider goes through `web_router` ... Calling a provider's API by any other route is not permitted.
- **R1.08** §2 Web access — P1 — built
  > The stage folder's dependency manifest lists `webrouter>=0.12.0`. ... Install it and the provider SDK dependencies from PyPI, including in the service's Docker build: `pip install "webrouter[search,extract,research]>=0.12.0"`
- **R1.09** §2 env — P4 — built
  > `NIMBLE_API_KEY` Credential for the `nimble` provider; `NIMBLE_BASE_URL` Base URL of the `nimble` provider endpoint; `TAVILY_API_KEY` Credential for the `tavily` provider; `TAVILY_BASE_URL` Base URL of the `tavily` provider endpoint
- **R1.10** §2 env — P4 — built
  > Keys are opaque non-empty strings. WebRouter's `nimble` provider reads `NIMBLE_API_KEY` and `NIMBLE_BASE_URL` from the environment, and its `tavily` provider reads `TAVILY_API_KEY`. A service that uses Tavily passes its base URL to WebRouter in `provider_config`: `provider_config={"tavily": {"api_base_url": <TAVILY_BASE_URL>}}`
- **R1.11** §2 limits — P1 — built (measure M1.3)
  > CPU 2 vCPU; Memory 3 GiB
- **R1.12** §2 limits — P1/P2 — built
  > Concurrent requests: up to 50 in flight
- **R1.13** §2 limits — P1 — built (measure M1.3)
  > Start to first healthy response: 60 s
- **R1.15** §2 limits — P1/P2 — built (measure M1.4)
  > Per-request timeout: 5 s (10 s for `POST /_test/reset`)
- **R1.16** §2 limits — P1/P4 — built
  > Outbound network: available during `docker build`; at run time, **only the provider endpoints this specification lists**. Disk: ephemeral; state need not survive a container restart
- **R1.17** §2 limits — P1 — built
  > Runtime assets and dependencies must be included in the image. This includes fonts, scripts and stylesheets; external services other than the provider endpoints this specification lists are unavailable at runtime.

### §3 Runtime contract
- **R1.18** §3.1 — P1 — built
  > Listen on `0.0.0.0` using the `PORT` environment variable, default `8080`.
- **R1.19** §3.2 — P1 — built
  > `GET /health  ->  200  {"status": "ok"}`
- **R1.20** §3.2 — P1 — built
  > Return 200 once the service and its data store can serve requests, within 60 seconds of container start. Non-200 responses are permitted before the service is ready. `/health` makes no provider call.
- **R1.21** §3.3 — P1 — built
  > `POST /_test/reset` with `{ ...fixture... }` -> `204 No Content`. Replace all service state with the fixture in the request body (§4).
- **R1.22** §3.3 — P1/P2 — built
  > When reset returns 204, subsequent requests must see only that fixture: no users other than the seeded ones, no dossiers and no stored idempotent responses. Repeated resets are supported.
- **R1.23** §3.3 — P2 — built
  > A build still running when reset is called must not change the state that follows the reset.
- **R1.24** §3.3 — P1 — built
  > This control endpoint must be enabled in the delivered image and requires no authentication.
- **R1.25** §3.4 — P1 — built
  > The service keeps a clock that only reset and `POST /_test/clock` move. Every timestamp the service records or returns is read from this clock.
- **R1.26** §3.4 — P1 — built
  > `POST /_test/clock` `{ "now": "2026-03-01T09:30:00+00:00" }` -> `204 No Content`
- **R1.27** §3.4 — P1 — built
  > Reset sets the clock to the fixture's `now`. Before the first reset the clock follows the system time.
- **R1.28** §3.4 — P1 — built
  > The clock stands still between calls: two requests with no clock call between them read the same time.
- **R1.29** §3.4 — P1 — built
  > `now` is an RFC 3339 timestamp with an explicit offset. A `now` earlier than the clock's current time is 422 `validation_failed` and changes nothing.
- **R1.30** §3.4 — P1 — built
  > `POST /_test/clock` requires no authentication.
- **R1.31** §3.5 — P1 — built
  > Requests and responses are `application/json; charset=utf-8`.
- **R1.32** §3.5 — P1 — built
  > Timestamps in responses are RFC 3339 with an explicit offset, e.g. `2026-09-24T19:00:00+02:00`.
- **R1.33** §3.5 — P1 — built
  > Unknown fields in a request body are ignored, never an error. Unknown query parameters are ignored. IDs are opaque strings of at most 64 characters. Their format is yours.

### §4 Model
- **R1.34** §4 Users — P1 — built
  > Users sign up and log in (§6). Every authenticated user sees the same dossiers.
- **R1.35** §4 Domains — P1 (shared util) — built
  > Every domain the API takes, in a body or a path, is first **normalised**: surrounding whitespace removed, lowercased, one trailing `.` removed, and one leading `www.` removed.
- **R1.36** §4 Domains — P1 — built
  > The normalised domain must then be a valid host name: two or more labels separated by `.`, each label 1 to 63 characters of `a-z`, `0-9` and `-`, not starting or ending with `-`, and 253 characters or fewer in total. Anything else, including a URL with a scheme or a path, is 422 `validation_failed`.
- **R1.37** §4 Domains — P2 — built
  > `Acme-Robotics.TEST.`, `www.acme-robotics.test` and `acme-robotics.test` name the same company and the same dossier. Responses always carry the normalised domain.
- **R1.38** §4 Fields — P2/P4 — built
  > A dossier has exactly these six fields: `legal_name` String; `hq_city` String (city, without region or country); `ceo` String (full name); `founded_year` Integer; `headcount_range` String: one of `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+`; `funding_total` Integer: total equity funding raised, in whole US dollars
- **R1.39** §4 Fields — P3 — built
  > A string value is written as the supporting excerpt writes it, without surrounding whitespace. A headcount the web states as a number, or as a range that fits inside one of the ranges above, has the range that contains it as its value.
- **R1.40** §4 Fields — P2 — built
  > Each field in a response has this shape: `{ "value": "Dana Ruiz", "status": "known", "citations": [ { "url": ..., "excerpt": ..., "provider": "nimble" } ] }`
- **R1.41** §4 Fields — P2/P4 — built
  > `status` is `known` when `value` is not null, and `unknown` when it is. A `known` field has one or more citations. An `unknown` field has `"value": null` and `"citations": []`.
- **R1.42** §4 Fields — P4 — built
  > `url` is the URL of the page the excerpt was served for, `provider` is `nimble` or `tavily`, the provider that served it.
- **R1.43** §4 Evidence — P4 — built
  > The **evidence** for a company is every page that some search, through any provider and for any query naming the company (as in Appendix A.2), returns, with its full text, and every claim that a `nimble` research run for the company asking for all six fields answers with.
- **R1.44** §4 Evidence — P4 — built
  > Of the searches that a provider answers without an error, every build makes exactly one whose query is exactly the company's normalised domain, through a provider of its choice; its other such searches use other queries. A search that a provider answers with an error does not count. The pages whose text a build obtains from providers are the pages it **gathers**.
- **R1.45** §4 Citation — P3/P4 — built
  > The excerpt is copied character for character from that served text, except that any run of whitespace may be written as a single space. It is 1 to 500 characters long. It is taken from the page's prose (below), not from its header.
- **R1.46** §4 Support — P3 — built
  > An excerpt **supports** a value when, read on its own, it states that value for that field of this company, as Appendix A defines. The excerpt may write the value differently from the API: `Acme Robotics has raised $12M.` and `Acme Robotics has raised 12 million dollars.` both support a `funding_total` of `12000000`, and `Acme Robotics employs about 120 people.` supports a `headcount_range` of `51-200`.
- **R1.47** §4 Support — P4 — built
  > A research answer carries a claimed value for a field and a citation for the claim. The claim is asserted only when its citation supports it. A field is `unknown` when no evidence supports a value for it, even when a research answer claims one.
- **R1.48** §4 Support — P4 — built
  > When the evidence supports more than one value for a field, the field holds one of them and cites only excerpts that support that value.
- **R1.49** §4 Pages — P3 — built
  > Every page has a URL, a title and a text. A text may begin with **header lines**, each of the form `Name: value`, where the name is a capitalised word or several joined by `-`. The header ends at the first empty line; everything after it is the page's **prose**. A text whose first line is not a header line has no header and is all prose.
- **R1.50** §4 Pages — P3 — built
  > The header line `Facts:` carries a JSON object on the same line. ... It is informative only: citations come from the prose, and whether an excerpt supports a value is decided by Appendix A alone. The service may ignore other header lines.
- **R1.51** §4 Fixture — P1 — built
  > Fixture: `{"now": ..., "users": [ {"id", "email", "password", "display_name"} ]}`. `now` is required and sets the clock (§3.4). Seeded users must be able to log in with the given password immediately.
- **R1.52** §4 Fixture — P1 — built
  > A fixture with two users sharing an email is a reset error: 422 `validation_failed`, changing nothing.

### §5 Errors
- **R1.53** §5 — P1 — built
  > Every 4xx and 5xx response carries this body: `{ "error": { "code": "not_found", "message": "human readable, any wording" } }`. Use the specified HTTP status and `code`.
- **R1.54** §5 table — P1 — built
  > 400 `malformed_request` Unparseable body, or a field of the wrong JSON type; 400 `missing_idempotency_key` Required `Idempotency-Key` header absent or empty; 401 `unauthenticated` Missing, malformed or unknown bearer token; 404 `not_found` No such resource, or not visible to this caller; 409 `idempotency_key_reuse` Key already used by this caller with a different request body; 422 `validation_failed` A required field or query parameter is missing, or a stated rule is violated with no more specific code
- **R1.55** §5 — P1 — built
  > A field of the correct JSON type with an invalid format or out-of-range value gives 422 `validation_failed`, unless an endpoint specifies a different error.
- **R1.56** §5 — P1/P2 — built
  > An integer-valued **query parameter** is written as plain decimal digits: `1e9`, `4.0` and `+4` are 422 `validation_failed` whatever their numeric value. Reserve 400 `malformed_request` for a body that does not parse or a field of the wrong type.
- **R1.57** §5 ranges — P1/P2 — built
  > `Idempotency-Key` 1 to 255 characters, else 422 `validation_failed`; `limit` integer 1 to 200, else 422; `offset` integer 0 or more, else 422
- **R1.58** §5 — P1/P2/P4 — built
  > Requests must not produce 5xx responses, including under concurrent load and when a provider endpoint answers with an error.

### §6 Authentication
- **R1.59** §6 — P1 — built
  > `POST /auth/signup {email, password, display_name}` -> `201 { "user_id", "display_name", "token" }`
- **R1.60** §6 — P1 — built
  > `POST /auth/login {email, password}` -> `200 { "user_id", "display_name", "token" }`
- **R1.61** §6 table — P1 — built
  > Email already registered: 409 `email_taken`; Password shorter than 8 characters: 422; `email` not of the form `local@domain`: 422; `display_name` empty or longer than 100 characters: 422; Wrong password or unknown email on login: 401 `unauthenticated`
- **R1.62** §6 — P1 — built
  > For a user seeded by the fixture (§3.3), `user_id` is that user's `id` in the fixture.
- **R1.66** §6 — P1 — built
  > Every other endpoint requires a bearer token, except `/health`, the `/_test/*` endpoints and the two above. A request to such an endpoint that lacks a valid token is 401 `unauthenticated`, even when it also lacks a required `Idempotency-Key`. `Authorization: Bearer <token>`
- **R1.67** §6 — P1 — built
  > Tokens do not expire. An account may have multiple valid tokens and concurrent sessions.
- **R1.68** §6 — P1 — built
  > Passwords must be stored using a password-hashing function such as bcrypt, scrypt or Argon2, or an equivalent. Plaintext password storage is not permitted.
- **R1.69** §6 — P1 — built
  > Email verification, password reset, refresh tokens and role-management endpoints are out of scope.

### §7 Idempotency
- **R1.70** §7 — P2 — built
  > Two write paths require an idempotency key (§8): **`POST /dossiers`** and **`POST /dossiers/{domain}/refresh`**. Everything below applies to each of them independently.
- **R1.71** §7 — P2 — built
  > The key is scoped to **the authenticated user**. Two different users may use the same key string with no interaction between them.
- **R1.72** §7 — P2 — built
  > A replay means the same user sending the **same method, the same path and the same body**. The same key with the same body on a different path is a different request, not a replay, and must succeed normally. `Acme-Robotics.test` and `acme-robotics.test` in a path or body are different requests for this rule, though they name the same dossier.
- **R1.73** §7 table — P2 — built
  > Header absent or empty: 400 `missing_idempotency_key`; First use of the key: the normal response (§8); Replay: same key, same body: **200**, body identical to the original response as a JSON value; Same key, different body: 409 `idempotency_key_reuse`; Key reused after the original request failed with 4xx: treated as a first use
- **R1.74** §7 — P2 — built
  > "Same body" means the same JSON value after parsing — key order and whitespace do not matter. Unknown fields are ignored (§3.5) and play no part in this comparison: a body that differs from the first only in unknown fields is the same body, so the request is a replay.
- **R1.75** §7 — P2 — built
  > `POST /dossiers/{domain}/refresh` takes no body; any body sent to it is ignored and plays no part in deciding a replay.
- **R1.76** §7 — P2 — built
  > For concurrent identical requests with an unused key, exactly one returns the normal response. The others return 200 with the same body. The operation takes effect only once.
- **R1.77** §7 — P2 — built
  > A successful replay returns the original response, even after the dossier has changed. It starts no build and makes no provider call.
- **R1.78** §7 — P2 — built
  > After the body has parsed as a JSON object and the caller is authenticated, an already claimed key is resolved before field validation. Thus changing a successful request to an invalid body with the same key still returns `409 idempotency_key_reuse`.

### §8 API — builds
- **R1.79** §8 Builds — P2 — built
  > A **build** researches one dossier: it calls the providers, decides each field, and replaces the dossier's fields with the result when it completes. A dossier's first build starts with `POST /dossiers`, and every later one with `POST /dossiers/{domain}/refresh`. A build's **time** is the clock's time when the request that started it was received.
- **R1.80** §8 Builds — P2 — built
  > A dossier has at most one build running at a time.
- **R1.81** §8 Builds — P2/P4 — built
  > A build ends in `ready` when it completed, or `failed` when none of its provider calls succeeded. A failed build leaves the fields as they were.
- **R1.82** §8 Builds — P4 — built (measure M1.5)
  > When a build completes `ready`, each field is `known` exactly when the evidence (§4) supports a value for it.
- **R1.83** §8 Builds — P4 — built (measure M1.2)
  > A build whose provider calls each answer within one second ends within 10 seconds of the request that started it.
- **R1.84** §8 Builds — P4 — built
  > That bound is not a deadline for slower providers. Against the live providers (`NIMBLE_BASE_URL` unset, or its host `sdk.nimbleway.com`), where a Nimble search can take over ten seconds and a research run about a minute, a build does not give up on a call that has been waiting less than 30 seconds, nor stop gathering because of the time it has run in its first 120 seconds. It still ends `ready` or `failed` within 300 seconds.
- **R1.85** §8 Builds — P1/P2 — built
  > Reading a dossier, listing dossiers and every other request except `POST /dossiers` and `POST /dossiers/{domain}/refresh` make no provider call.

### §8 `POST /dossiers`
- **R1.86** §8 — P2 — built
  > `POST /dossiers` with `{ "domain": "acme-robotics.test" }` -> `202 { "dossier_id": "d_7", "domain": "acme-robotics.test", "state": "building" }`. `Idempotency-Key` is required; see §7.
- **R1.87** §8 — P2 — built
  > When no dossier exists for the domain, the service creates one, starts its first build and returns 202. When a dossier already exists for the domain, the service starts no build and returns **200** with that dossier's `dossier_id`, `domain` and current `state`.
- **R1.88** §8 — P2 — built
  > Concurrent requests for the same domain create one dossier and start one build, whatever their keys.
- **R1.89** §8 — P2 — built
  > `domain` missing: 422 `validation_failed`; `domain` invalid after normalisation (§4): 422 `validation_failed`

### §8 `GET /dossiers/{domain}`
- **R1.90** §8 — P2 — built
  > Response: `dossier_id`, `domain`, `state`, `researched_at`, `spent_units`, `fields` (all six).
- **R1.91** §8 — P2 — built
  > `state` is `building` while a build runs, otherwise the outcome of the latest build, `ready` or `failed`.
- **R1.92** §8 — P2 — built
  > `fields` always holds all six fields. Before the first build completes `ready`, every field is `unknown`. While a later build runs, `fields` are those of the last build that completed `ready`.
- **R1.93** §8 — P2 — built
  > `researched_at` is the time of the last build that completed `ready`, or null.
- **R1.94** §8 — P2/P4 — built
  > `spent_units` is the total cost (§9) of every provider call made for this dossier, by every build, since it was created.
- **R1.95a** §8 — P2 — built
  > The domain in the path is normalised (§4). No dossier for it is 404 `not_found`.

### §8 `POST /dossiers/{domain}/refresh`
- **R1.106** §8 — P2 — built
  > `Idempotency-Key` is required; see §7. No body. Starts a new build of the dossier and returns 202 with `{ "dossier_id", "domain", "state": "building" }`. A refresh received while a build of the dossier is running starts no second build and returns 202 with the same body.
- **R1.107** §8 — P2/P4 — built
  > A refresh researches again: its build makes provider calls whether or not anything has changed since the last build, and its spending counts in `spent_units`.
- **R1.108** §8 — P2 — built
  > No dossier for the domain: 404 `not_found`

### §8 `GET /dossiers`
- **R1.109** §8 — P2 — built
  > `GET /dossiers?q=acme&limit=50&offset=0` -> `{ "dossiers": [ { "dossier_id", "domain", "state", "legal_name", "researched_at", "spent_units" } ], "has_more": false }`
- **R1.110** §8 — P2 — built
  > `legal_name` is the value of the dossier's `legal_name` field, or null.
- **R1.111** §8 — P2 — built
  > `q` is optional. When present, only dossiers whose domain or `legal_name` contains `q`, compared case-insensitively, are listed. An empty `q` lists every dossier.
- **R1.112** §8 — P2 — built
  > Dossiers are ordered by domain ascending.
- **R1.113** §8 — P2 — built
  > `limit` defaults to 50, range 1 to 200. `offset` defaults to 0. `has_more` is true when items exist beyond the last one returned.

### §9 Providers and cost
- **R1.141** §9 — P4 — built (measure M1.1)
  > Costs: nimble search lite 1, fast 5, deep 15; tavily search lite 8, fast 16, deep 16; extract nimble 1 per URL requested, tavily 2 per URL requested (including a URL for which no page is returned); research run through nimble 25 when started; checking on or collecting a run costs nothing.
- **R1.142** §9 — P4 — built
  > A search's depth is WebRouter's `search_depth`. A search returns at most 10 results, whatever number it asks for.
- **R1.143** §9 — P4 — built
  > A call that a provider refuses with an error status costs nothing. A call whose answer does not arrive, because it times out or its connection fails, costs its units as in the table, whether or not the provider received it. An extract that the provider answers with no page for the URL is not refused: it costs its units, as in the table, whatever status says so.
- **R1.144** §9 — P4 — built
  > An extract through `nimble` does not set `render`.
- **R1.148** §9 — P4 — built (measure M1.1)
  > A build stops making provider calls before its spending would exceed 80 units, and completes with the pages and research claims it has obtained.
- **R1.149** §9 — P4 — built
  > A research request names the company by its domain in its query, and names the fields it asks for by the field names in §4, as the property names of its output schema.

### §10 Export and import
- **R1.114** §10 — P2 — built
  > The service must support `GET /_test/export` and `POST /_test/import`. Like reset, these are unauthenticated control endpoints. Return 200 from export with a JSON object containing `track: "dossier"`, `format_version: 1` and `state` (an implementation-defined JSON object). The state format is opaque to the caller and must be accepted unchanged by import.
- **R1.115** §10 — P2 — built
  > Import takes that entire object and atomically replaces the service's state, returning 204. It must accept an unchanged export produced by this service. No dependency on the source process, files, volume, port or network address is allowed. Import is replacement, not merge; repeating it restores the exported state without duplicating anything.
- **R1.116** §10 — P2 — built
  > Invalid JSON follows §5; missing fields, wrong track/version or an invalid state give 422 `validation_failed` without changing the destination. These control calls have a 10-second timeout. Export is an atomic, read-only snapshot; subsequent source writes do not change it.
- **R1.117** §10 — P2 — built
  > Preserve accounts and hashed-password login, existing bearer tokens, dossiers with their ids, states, fields, citations, `researched_at` and `spent_units`, all completed idempotent request bodies and original responses. Identities and timestamps must not be regenerated.
- **R1.118** §10 — P2 — built
  > Import makes no provider call: imported dossiers are not researched again, and their citations remain citations served to this service. Failed request keys remain reusable. Existing tokens and retries must remain valid after import; replacing the state with a fresh fixture does not satisfy this requirement.
- **R1.119** §10 — P2 — built
  > Import removes all previous destination data and credentials. Reset clears all state, including imported state. Export and import do not change the clock. State need not survive an abrupt container restart.
- **R1.120** §10 — P2 — built
  > An export taken while a build is running holds the dossier as it was before that build; after import, that dossier is in the state of its last completed build, or `failed` with every field `unknown` when no build had completed.

### §11 Concurrency
- **R1.120a** §11 — P2 — built
  > Concurrent requests must produce the same results as executing them one at a time in some order. The requirements above hold at every read.

### Appendix A — support
- **R1.121** A.1 — P3 — built
  > A page's prose is split into lines at each line break, and each line into sentences. A sentence ends after a `.`, `!` or `?`, together with any `"`, `”`, `’` or `)` directly after it, when whitespace follows. A `.` that ends one of the legal-form suffixes in A.4, written as a whole word, does not end a sentence. Each sentence is taken without its surrounding whitespace; empty sentences are dropped.
- **R1.122** A.1 — P3 — built
  > An excerpt is a **single sentence** when, with every run of whitespace written as one space, this rule splits it into exactly one sentence.
- **R1.123** A.2.1 — P3 — built
  > It is a single sentence (A.1).
- **R1.124** A.2.2 — P3 — built
  > It names the company: it contains the company's normalised domain, or the company's name. The company's name is the first label of its domain with each `-` read as a space: `acme-robotics.test` is named by `Acme Robotics`.
- **R1.125** A.2.3 — P3 — built
  > It contains a statement phrase for F (A.3).
- **R1.126** A.2.4 — P3 — built
  > It contains none of the negating phrases (A.3).
- **R1.127** A.2.5 — P3 — built
  > It contains at least one value in F's format (A.4), and every value in F's format that it contains normalises to V (A.5).
- **R1.128** A.2 — P3 — built
  > The company's name, its domain and every phrase are matched without regard to case and as whole words: the characters directly before and after the match are not letters or digits. Phrases with a space match one space.
- **R1.129** A.2 examples — P3 — built
  > `Dana Ruiz has led Acme Robotics as chief executive since 2021.` → `ceo` `Dana Ruiz`; `Acme Robotics CEO: Sam Ortiz.` → `ceo` `Sam Ortiz`; `Acme Robotics was founded in 2014.` → `founded_year` `2014`; `Acme Robotics employs about 120 people.` → `headcount_range` `51-200`; `Acme Robotics is reportedly in talks to raise $40M.` → nothing: a negating phrase; `Acme Robotics opened a sales office in Porto.` → nothing: no statement phrase for `hq_city`
- **R1.130** A.3 — P3 — built
  > Statement phrases: `legal_name`: `legal name`, `registered name`, `registered as`, `registered company`, `legal entity`, `name of record`; `hq_city`: `headquartered in`, `headquarters in`, `head office in`, `based in`, `registered office in`, `registered seat in`; `ceo`: `chief executive officer`, `chief executive`, `CEO`; `founded_year`: `founded`, `founding`, `established`, `incorporated`; `headcount_range`: `employs`, `employees`, `staff`, `people`, `headcount`, `workforce`; `funding_total`: `raised`, `funding`, `invested`, `investment`
- **R1.131** A.3 — P3 — built
  > The negating phrases are: `in talks to`, `plans to`, `planning to`, `wants to`, `expects to`, `hopes to`, `aims to`, `seeking`, `could`, `would`, `might`, `reportedly`, `rumoured`, `former`, `formerly`, `will become`, `not`.
- **R1.132** A.4 — P3 — built
  > A **capitalised word** is an uppercase letter followed by one or more lowercase letters, with no letter or digit directly before or after it. The letters may be of any alphabet: `Zürich` and `Müller` are capitalised words. An **uppercase word** is two or more uppercase letters, with no letter or digit directly before or after it: `AI`, `USA`.
- **R1.133** A.4 — P3 — built
  > A **number** is written in digits, optionally with a `,` before each group of three digits and a decimal part after a `.`: `120`, `1,200`, `12.5`, `12,000,000`. Digits directly next to a letter, or joined to other digits by `,` or `.` in any other way, are not a number.
- **R1.134** A.4 legal_name — P3 — built
  > The company's name or its domain (matched as in A.2), then zero or more capitalised or uppercase words each after one space, then an optional `,`, one space, and a legal-form suffix with no letter or digit directly after it. Where several such texts start at the same place, the shortest counts
- **R1.135** A.4 hq_city — P3 — built
  > A place name directly after a statement phrase for `hq_city` and one space: the longest run of capitalised words joined by single spaces or by `-` that starts there, not part of a longer such run
- **R1.136** A.4 ceo — P3 — built
  > A person's name: a run of two or three capitalised words joined by single spaces that is not part of a longer such run. Occurrences of the company's name and of the statement phrases for `ceo` are first taken out of the sentence and separate the words around them
- **R1.137** A.4 founded_year — P3 — built
  > A number of exactly four digits, from 1800 to 2099, that is not part of an amount
- **R1.138** A.4 headcount_range — P3 — built
  > A number with no decimal part, 1 or more, that is not part of an amount. Words before it, such as `about` or `roughly`, do not change it. A stated range such as `51-200 employees` holds two numbers
- **R1.139** A.4 suffixes & amounts — P3 — built
  > The legal-form suffixes, matched exactly as written here: `Inc.`, `Corp.`, `LLC`, `LLP`, `L.P.`, `Ltd`, `Limited`, `Pty Ltd`, `plc`, `PLC`, `GmbH`, `AG`, `KG`, `SE`, `AS`, `A/S`, `ASA`, `AB`, `Oy`, `Oyj`, `B.V.`, `N.V.`, `S.A.`, `S.A.S.`, `S.L.`, `S.r.l.`, `S.p.A.`, `s.r.o.`, `a.s.`, `K.K.`. An **amount** is written in one of these forms, matched without regard to case, with no letter or digit directly before it or after it: `$`, `US$` or `USD`, an optional space, a number, and optionally a scale: `k`, `m`, `mn` or `bn` directly after the number, or one space and `thousand`, `million` or `billion`. ... A number, optionally one space and `thousand`, `million` or `billion`, then one space and `dollars` or `US dollars`. ... Amounts in other currencies are not amounts.
- **R1.140** A.5 — P3 — built
  > `legal_name`, `hq_city`, `ceo`: The text as the excerpt writes it; `founded_year`: The number as an integer; `headcount_range`: The range of §4 that contains the number; `funding_total`: The number times the scale (`k` and `thousand` 1,000; `m`, `mn` and `million` 1,000,000; `bn` and `billion` 1,000,000,000) in US dollars. An amount that does not come to a whole number of dollars is not a value

## Rulings (stage 1)

- **L1.01 Stack and module interface.** Python 3.12, one process, one asyncio event loop (Starlette or FastAPI on uvicorn, single worker), in-memory state guarded by one lock. Reason: §2 requires `web_router` in-process or in a Python helper; one process keeps §11 serialisability simple; §2 allows ephemeral state. Interface owned by `@builder-b` in `stage-1/app/research/__init__.py`:
  `async def run_build(domain: str, spend: Callable[[int], None]) -> dict` returning `{"ok": bool, "fields": {<six fields>: {"value", "status", "citations": [{"url","excerpt","provider"}]}}}`. `spend(units)` is called once per provider call with its cost (§9), including calls that time out; `ok` is false exactly when none of the build's provider calls succeeded. `@builder-a` calls it from the build orchestrator and uses its own stub only while `app.research` is absent.
- **L1.02 Check order on the two write paths.** Auth (401) → for `POST /dossiers`, body must parse as a JSON object (400 `malformed_request`) → `Idempotency-Key` absent/empty (400 `missing_idempotency_key`) → key longer than 255 (422) → claimed key: replay (200) or different body (409) → field validation (`domain` wrong type 400, missing/invalid 422) → path domain invalid 422 → 404. Reason: §6 puts 401 first; §7 resolves a claimed key only "after the body has parsed as a JSON object and the caller is authenticated".
- **L1.03 Replay identity.** Stored per (user, method, raw path as sent, key); the compared body for `POST /dossiers` is `{"domain": <value as sent>}` (unknown fields dropped, domain not normalised); for refresh the body is ignored. Only 2xx responses are stored; any 4xx leaves the key unclaimed. A replay returns status 200 and the stored body unchanged.
- **L1.04 Path domains.** `GET /dossiers/{domain}` and refresh with a domain invalid after normalisation → 422 `validation_failed` (§4 "Every domain the API takes, in a body or a path").
- **L1.05 Clock rendering.** Timestamps are rendered as RFC 3339 with the offset of the last `now` set (UTC `+00:00` before the first reset), seconds precision unless the input carried fractions. `now` missing → 422; not a string → 400; no offset or unparseable → 422; equal to the current time → 204.
- **L1.06 Fixture validation.** Reset body not a JSON object → 400; `now` missing/invalid → 422; `users` absent → no users; a user entry with a field of the wrong type → 400, missing field → 422; duplicate email → 422. On any error nothing changes.
- **L1.07 Emails.** Compared case-insensitively for uniqueness and login, stored and returned as given. `local@domain` means exactly one `@`, non-empty local and domain parts, no whitespace. Password length counted in characters (code points). `display_name` empty means `""` or whitespace-only.
- **L1.08 Signup precedence.** Type errors 400 → missing/invalid fields 422 → 409 `email_taken`.
- **L1.09 IDs and tokens.** Signed-up user ids `u_<random hex>`, dossier ids `d_<random hex>`; tokens are ≥ 128-bit random url-safe strings; the `Bearer` scheme word is case-insensitive; anything else in `Authorization` is 401.
- **L1.10 Unknown routes.** Unknown path → 404 `not_found`; known path with unsupported method → 405 with the §5 error body, code `not_found`. No framework default bodies anywhere.
- **L1.11 Research citations.** A research claim's citation may be cited directly (provider `nimble`, its `url`, its excerpt verbatim) only when that excerpt, on its own, supports the claim under Appendix A. Any other citation is a whole sentence (A.1) of the prose of a page a provider served, whitespace runs collapsed, 1–500 characters.
- **L1.12 Multiple supported values.** Hold the value with the most supporting excerpts on distinct URLs; ties broken deterministically (first gathered). Cite only excerpts supporting the chosen value; at most 5 citations per field.
- **L1.13 Failed vs ready.** `failed` exactly when no provider call of the build succeeded (every call errored or timed out). Otherwise `ready`, even if every field is `unknown`.
- **L1.14 Reset/import during a build.** A build started before a reset or import must not write anything (fields, state, `spent_units`) into the state that follows; use a generation counter checked under the lock.
- **L1.15 Export during a build.** The export holds that dossier with the fields, `researched_at` and `spent_units` it had before the running build began, and the state of its last completed build (`failed` with every field `unknown` if none completed). Stored idempotent responses are exported verbatim.
- **L1.16 Import validation.** Body not JSON → 400; not an object, `track` ≠ `"dossier"`, `format_version` ≠ integer 1, `state` missing or not in this service's own shape → 422, nothing changes.
- **L1.17 Listing.** `q` is matched raw (not normalised) against the normalised domain and the `legal_name` value, case-insensitively. Empty `limit`/`offset` values are 422.
- **L1.18 Live timeouts.** "Live" means `NIMBLE_BASE_URL` unset or its host is `sdk.nimbleway.com`. Live: per-call timeout ≥ 30 s (research ≤ ~120 s), whole build ≤ 280 s. Mock (any other base URL): per-call timeout short enough that a build whose calls answer within 1 s ends within 10 s.
- **L1.19 Tests location.** Builders' unit tests live under `stage-1/tests/`; the Prover's black-box suite lives under `acceptance/stage-1/` at the repo root. The Dockerfile must not need either.
- **L1.20 Sequencing of standalone modules.** A package that cannot run on its own (P3) is reviewed statically and by its unit tests as soon as it lands, then merged on top of the accepted P1 and accepted or rejected on that integrated candidate's build, Prover suite and event check. End-to-end citation/support evidence is judged on P4. Reason: the Gatekeeper's mandate requires building and starting the exact revision.
- **L1.21 Check invocation.** The event check runs as the dispatch gives it, with only `--repo` pointed at the Gatekeeper's throwaway candidate checkout before ACCEPT, and again at `main` after the merge (fresh `--out` each time, `checks/s1-<n>`); the harness's own `df-*` resources and dynamic ports are authorised by the dispatch and serialised by the flock. RUN.md smoke runs may swap only the image/container name (gatekeeper prefix) and host port (18300–18399). A merge whose post-merge check fails is reverted with a new commit and rejected.
- **L1.22 Mock-mode timeouts.** With a non-live base URL, per-call timeout ≥ 11 s (the mock's delay fault is at most 10 s) and build deadline ≈ 25 s (the event check settles for 30 s); phases stay parallel so ≤1 s calls end well within 10 s. Reason: §8 "That bound is not a deadline for slower providers"; abandoning an answering provider loses fields for no gain.
- **L1.23 Budget is a cap.** Spending up to 80 units for more recall (second search wave, extra extracts) is a correctness gain under R1.82/R1.43, not a cost regression; the hard 80-unit cap and log-sum = spend-sum stay mandatory.
- **L1.24 Evidence boundary.** A value may be asserted only from (a) a prose sentence of a page some search of the build returned (text from that search or from extracting that URL), or (b) a research claim whose cited excerpt, whole, is a single sentence supporting the claimed value (cited verbatim). Research excerpts are never split; a page reached only through a research citation is not evidence. Reason: §4 evidence definition and R1.47.
- **L1.25 Coverage of deployment/inspection ids.** Container ids (R1.03–R1.05, R1.08, R1.11, R1.13, R1.16–R1.18) are covered by named tests in the Prover's isolated Docker runner; R1.68 by a black-box test that the plaintext password is absent from the export; R1.00, R1.07, R1.69 and R1.84 are inspection-only, verified by the Gatekeeper with evidence in its verdict (R1.84 also by builder-b's virtual-time unit tests).

## Verdict log (stage 1)

- 19:5xZ P1 (builder-a b27b298) handed off; P3 (builder-b 0af9832) handed off. Statuses → built.
- 20:1xZ P2 (builder-a 3581e5f, includes P1) handed off. P2 statuses → built (R1.82–R1.84 stay open until P4).
- P5 added for builder-a: limits and robustness (R1.12, R1.15, R1.23, R1.58, R1.76, R1.88, R1.120a; measures M1.3, M1.4).
- 20:4xZ P5 (builder-a 467ab72) handed off: 50-worker load, 0 5xx, max latency 1.48 s, reset under load 1.42 s (M1.4 met on stub/stand-in). Gatekeeper preliminary findings on P2 3581e5f: reset racing an in-flight POST leaks a dossier (R1.22/R1.120a); offset of 5000 digits → 500 (R1.57/R1.58). P3 0af9832 finding: funding Decimal precision (R1.140), no test names ledger ids, .pyc committed. Fixes assigned to the owners.

- 21:0xZ builder-a fix 0eca7a7 (reset race → 401, huge query ints) supersedes 467ab72. P4 (builder-b 8c066a5, includes P3) handed off: 50–57 units/build on sample corpus (M1.1), 50 concurrent builds 6.5 s. Follow-ups to builder-b: P3 findings, L1.22, spend spare budget on extracts.
- 21:2xZ REJECT 467ab72 (builder-a, superseded by 0eca7a7/60af80c): reset race (R1.120a) and 5000-digit offset 500 (R1.57/R1.58) reproduced; event check s1-1: 118 passed, 4 failed — the 4 are R1.81/R1.82/R1.111 research-dependent cases expected on the stub. Change: none needed beyond the fixes already in 0eca7a7.
- 21:4xZ builder-b fix e51c627 supersedes 0af9832/8c066a5: exact funding arithmetic (R1.140), L1.22 timeouts (delay 5 s → ready 10.9 s; 10 s → 20.3 s; 1 s → 2.3 s), second search wave, all tests name ids (163). M1.1 now 58–65 units/build (was 50–57). Integrated candidate: builder-a 60af80c + builder-b e51c627. P7 (live-mode assurance) assigned to builder-b; P6 (integration rehearsal) running on builder-a.
- 21:5xZ P7 (builder-b 0cf2c08, includes e51c627): live-mode timing proven with virtual-time unit tests; defect fixed: empty NIMBLE_BASE_URL was treated as live. R1.84 built. Candidate: builder-a 60af80c + builder-b 0cf2c08. P8 (epoch-change sweep + repo README.md) to builder-b. FACTORY.md written by lead.
- 22:0xZ P6 (builder-a) integration rehearsal found a defect: one leaked AsyncWebRouter per build (per-build event loop) → 1017 fds, 'Too many open files', 16/22 prover tests failed. Fixed in builder-a 1aa751a (one shared engine loop). After fix: prover suite 22/22 OK, load 0 5xx max 2.43 s, reset under load 2.31 s, reset/export during 10 builds correct. Candidate: builder-a 1aa751a + builder-b 0cf2c08. P9 (cleanup: .dockerignore, remove stub, fd-leak regression, RUN.md from fresh clone) to builder-a.
- 22:1xZ P8 (builder-b 4bfe432): epoch-1 refresh sweep — all 12 companies refreshed with full calls, cumulative spent_units, max build 67 units, epoch-1 values match key, citations verified; no engine defect. Repo README.md added. P10 (live-evidence tool tools/live-runway.sh, not run — no live key) to builder-b. Gatekeeper reminded that the candidate must include builder-a 1aa751a (fd-leak fix).
- 22:2xZ Gatekeeper finding on e51c627: a two-sentence research excerpt was split and its first sentence used (R1.47/R1.123) → ruling L1.24, fix assigned to builder-b. Prover suite of record b6c2ec4: 23/23 pass on combined candidate 401e78d (46 custom-corpus cases). P10 (builder-b deec22f): tools/live-runway.sh, dry-run against mock only.
- 22:3xZ builder-b da12b20/97530c9: research excerpt no longer split (R1.47/R1.123); L1.24 confirmed — no research-only URL is ever extracted (regression tests added, 178 pass). Units unchanged 58–65. Candidate: builder-a latest + builder-b 97530c9. P11 (peer review of builder-a's area) to builder-b.
- 22:4xZ builder-a candidate a76f428 (supersedes 467ab72/0eca7a7/60af80c/1aa751a): shared engine loop, hashing pool, reset-race and huge-int fixes, .dockerignore; 32 api tests; integration rehearsal: prover suite OK, fds 10, load 0 5xx max 2.50 s. builder-b head 366ef88. Risk found by builder-a: concurrent builds slow (10 → 9–15 s, 12 → 17 s) threatens R1.83/M1.2 → builder-b priority fix. Integrated candidate: a76f428 + 366ef88.
- 22:5xZ P9 (builder-a bb11a6e, merges builder-b 0cf2c08): stub removed (research imported directly), fd-leak regression test (fails on per-build loops), RUN.md rewritten and checked from a fresh clone; 33 api tests. Integrated candidate: bb11a6e + 366ef88 (+ pending builder-b R1.83 concurrency fix). Prover suite head 9f48e7b; asked to add R1.83-under-concurrency and R1.06 Tavily-absent tests. P12 (peer review of research engine) to builder-a.
- 22:5xZ REJECT e51c627 (builder-b) on combined 401e78d (60af80c + e51c627): R1.47/R1.123 research excerpt split; missing test names. Same run: acceptance 22/22, event check s1-2 **122/122 passed**; Prover suite missed a `hopes to` mutation (→ phrase-table-generated corpus cases). Change: fixed in builder-b da12b20/366ef88; L1.24 recorded.
- 23:0xZ builder-b 4bb0268: R1.83 concurrency fix (limiter 24→200, one shared router per loop, load-aware second wave): 20 concurrent builds with 1 s delay max 6.3 s (was 25.9 s), units 52–60. P11 peer review of builder-a: one defect (`_DIGITS` `$` matches a trailing newline → `limit=5%0A` gives 200) → builder-a fix. Next candidate: builder-a bb11a6e(+fix) + builder-b 4bb0268.
- 23:1xZ P12 (builder-a review of research engine): no concrete defect; fault matrix shows spent_units == mock log sum ≤ 80 and exactly one answered domain search in every scenario; hardening note (_NoPage outside extract) → builder-b. builder-a 619df05: anchor fixes (query ints, domain labels, RFC 3339) with tests. Integrated candidate: builder-a 619df05 + builder-b 4bb0268. Lead head 84755b2 handed to gatekeeper.
- 23:2xZ builder-a load rehearsal on 619df05 + 4bb0268: 3971 req, 0 5xx, max 2.17 s, reset under load 2.01 s, fds 36 (M1.4 met); units/build 50–65, service sum 750 == mock log 750 (M1.1); 12 concurrent builds ≤1.8 s (M1.2). builder-b final head bfa350e (5c6faee gateway hardening + R1.58 tests). Candidate: builder-a 619df05 + builder-b bfa350e.
