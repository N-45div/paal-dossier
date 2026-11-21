# Dossier — requirements ledger (cumulative)

Track: dossier. Repository: /home/ndivij/buildathon/band-work/paal-dossier (main, merged only by @gatekeeper).
Stage 1 started: 2026-11-21T05:08Z.

Statuses: `open` → `built` (builder handed off) → `tested` (Prover test exists and passes against it) → `accepted` (Gatekeeper accepted).
The status of every entry is tracked in the **Status table** at the end of this file (per package), and updated per verdict; the per-entry `[open]` tags below are the stage-start baseline.
The `[pkg X]` tag is the primary owner; the package definitions below say which sections each package owns.

## Packages (stage 1)

| Pkg | Owner | Scope | Order |
|---|---|---|---|
| PA1 | @builder-a | Service skeleton: Python HTTP server on `PORT`, `/health`, error envelope and validation conventions (§5), reset/clock (§3.3, §3.4), auth signup/login with hashed passwords and bearer tokens (§6), fixture handling (§4), `Dockerfile`, `RUN.md`, `requirements.txt` (`webrouter[search,extract,research]>=0.12.0`), resource limits (§2) | 1st — must build and start first |
| PA2 | @builder-a | Dossier API (§8): POST /dossiers, GET /dossiers/{domain}, refresh, list; idempotency (§7); build lifecycle state machine calling `app.research.run_build`; export/import (§10); concurrency (§11); domain normalisation (§4) | after PA1 |
| PB | @builder-b | `app/support.py`: pure implementation of Appendix A + §4 Fields/Pages/header parsing/citation rules (sentence splitting, supports-rule, value formats, normalisation, excerpt validation). Exhaustive unit tests. | 1st (parallel with PA1) |
| PC | @builder-b | `app/research.py`: provider adapter over `web_router` (search/extract/research, cost accounting, 80-unit budget, timeouts, error handling), build strategy, field decision and citation selection (§1 rules, §4 evidence, §8 builds, §9) | after PB (start WebRouter investigation early) |
| PT | @prover | Independent black-box acceptance tests from the spec (HTTP, run against the Docker image + the mock web), in `tests/acceptance/` | in parallel from the start |
| GK | @gatekeeper | Review, check runs, merging, final isolated check | as packages land |

## Rulings

- **Rul-1 (language/runtime).** Python 3.12 slim image, single process (all state in memory under asyncio locks, so §11 holds trivially), `web_router` called in-process. Web framework is builder-a's choice (Starlette/FastAPI+uvicorn or aiohttp), must be async and handle 50 concurrent requests under 2 vCPU / 3 GiB. No other provider route: never call a provider's API or SDK except via `web_router`.
- **Rul-2 (module contract, so PA2 and PC integrate).** `app/research.py` exposes `async def run_build(domain: str) -> BuildOutcome` where `BuildOutcome` is a dataclass `(ok: bool, spent_units: int, fields: dict[str, FieldResult])`; `ok=False` iff no provider call succeeded; `spent_units` is the cost of this build's calls (counts even when `ok=False`); `fields` holds all six field names, each `FieldResult(value, citations)` with `value=None, citations=[]` for unknown and citations as dicts `{"url","excerpt","provider"}`. `app/support.py` (PB) exposes: `FIELDS`, `split_header(text)->(headers: dict[str,str], prose: str)`, `supported_values(domain: str, excerpt: str) -> dict[str, object]` (field→normalised value for every field the excerpt supports under A.2), `extract_supports(domain, prose) -> list[Support(field,value,excerpt)]` (single-sentence excerpts of the prose), `excerpt_in_prose(prose, excerpt) -> bool` (character-for-character copy with whitespace runs collapsible, 1–500 chars). PA1 owns `app/domain.py` (`normalise_domain(raw) -> str|None`). PA2 ships a placeholder `app/research.py` (all-unknown, spent 0) that PC replaces entirely; on merge conflicts on that file PC's version wins.
- **Rul-3 (cost accounting).** A budget ledger reserves a call's full cost *before* issuing it (a timed-out or dropped call costs its full units); a call refused with an error status releases the reservation (costs 0). A call is only issued when `spent + cost <= 80`. `spent_units` of a dossier accumulates every build's spent units, including failed builds. Extract cost is per URL requested (nimble 1, tavily 2). Never use nimble `deep` search/ `render`.
- **Rul-4 (build outcome).** A build ends `failed` only when no provider call succeeded; it then leaves fields and `researched_at` unchanged but its spend still counts. Otherwise `ready`, replacing all six fields and setting `researched_at` to the build time (clock at request receipt). A refresh while building returns 202 with the same body and starts nothing.
- **Rul-5 (idempotency storage).** Per (user, endpoint-kind, key) store `(method, path as written, canonical parsed body minus unknown fields, original status+body)`. Same key+same method/path/body → 200 with the original *body*; same key different body → 409; same key different path → independent request (key scope includes the path). 4xx originals are not stored (key reusable). A key claimed by an in-flight request: concurrent identical requests wait for the first and return 200 with its body. Order of checks: auth (401, which precedes every 400) → missing/empty key (400) → body parse (400) → key length (422) → claimed key (409/replay) → field validation (422).
- **Rul-6 (reset vs running builds).** Every build carries the state generation at its start; a build finishing after a reset/import discards its result. Reset replaces users, dossiers, idempotency records, tokens and the clock.
- **Rul-7 (export during a build).** Export serialises each dossier as of before its running build: `state` = the last completed build's outcome, or `failed` with six unknown fields if no build ever completed; its spent_units as of before the running build is not required to include in-flight spend beyond what was recorded — use the recorded value at the snapshot instant.
- **Rul-8 (choosing among supported values).** When the evidence supports several values for a field, pick the value supported by the most distinct pages (ties: the value whose first supporting excerpt is earliest in gather order), cite only excerpts that support it, up to 3 citations. Every excerpt is a whole single sentence from page prose (never the header, never from `Facts:`), verified with `excerpt_in_prose` against text a provider actually served in this build. Research claims count as evidence only when their citation supports the claimed value via `supported_values`.
- **Rul-9 (gathering strategy, PC).** Exactly one successful search whose query is exactly the normalised domain (retry through the other provider or again on error — errored searches do not count); other successful searches use different queries naming the company. Prefer nimble `lite` searches for URL discovery (1 unit) and nimble `extract` for full text (1 unit per URL, no `render`), plus one nimble research run (25 units) asking for all six field names; stay under 80 total and run independent calls concurrently so a build ends well within 10 s when providers answer within 1 s. Tavily is optional and never required. Unset/empty provider env must not crash the service.
- **Rul-10 (non-5xx).** No request may produce 5xx: provider failures become build state `failed`; unexpected exceptions in handlers are mapped to a valid non-5xx error only where a spec error code fits, otherwise treated as bugs to fix.

## Requirements (spec stage-1.md; every quote is verbatim; status: open | built | tested | accepted)

### R1.1  [pkg ALL] [accepted]
- Section: Dossier — Stage 1: company profiles (spec line 3)
- Text:

> This stage defines the initial service and its API.

### R1.2  [pkg ALL] [accepted]
- Section: Dossier — Stage 1: company profiles (spec line 5)
- Text:

> Build from the supplied requirements.

### R1.3  [pkg ALL] [accepted]
- Section: Dossier — Stage 1: company profiles (spec line 5)
- Text:

> Source code, API documentation and schemas from existing products in this domain must not be used.

### R1.4  [pkg ALL] [accepted]
- Section: Dossier — Stage 1: company profiles (spec line 5)
- Text:

> WebRouter's own documentation may be used.

### R1.5  [pkg PA2] [accepted]
- Section: 1. Scope (spec line 11)
- Text:

> A caller asks for a company by its web domain.

### R1.6  [pkg PA2] [accepted]
- Section: 1. Scope (spec line 11)
- Text:

> The service researches the company on the web and keeps a **dossier**: a profile of six fields, each with the value the web supports and the excerpts it came from.

### R1.7  [pkg PA2] [accepted]
- Section: 1. Scope (spec line 11)
- Text:

> A dossier is built in the background, read any number of times, and refreshed on request.

### R1.8  [pkg PA2] [accepted]
- Section: 1. Scope (spec line 11)
- Text:

> Only the HTTP API is required.

### R1.9  [pkg PA2] [accepted]
- Section: 1. Scope (spec line 16)
- Text:

> The following apply to all operations, including concurrent requests and retries:

### R1.10  [pkg PC] [accepted]
- Section: 1. Scope (spec line 18)
- Text:

> 1. Every value the service asserts cites at least one excerpt that a provider endpoint served
>    to this service, and that excerpt supports the value. No citation is invented, reworded, or
>    attached to a value it does not support.

### R1.11  [pkg PC] [accepted]
- Section: 1. Scope (spec line 21)
- Text:

> 2. No build of a dossier spends more than 80 units (§9).

### R1.12  [pkg PA2] [accepted]
- Section: 1. Scope (spec line 23)
- Text:

> Contact data, people search, and fields other than the six in §4 are out of scope.

### R1.13  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 27)
- Text:

> Deliver an HTTP service, a `Dockerfile` and a `RUN.md` with a command that builds and starts the service without manual setup.

### R1.14  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 27)
- Text:

> Language, framework and storage are unrestricted.

### R1.15  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 27)
- Text:

> A `docker-compose.yml` is optional.

### R1.16  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 31)
- Text:

> The submission is a containerized HTTP service, not a Python package.

### R1.17  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 31)
- Text:

> Python is not required in the implementation.

### R1.18  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 31)
- Text:

> TypeScript/JavaScript, Go, Rust, Java, Python and any other language are equally valid.

### R1.19  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 31)
- Text:

> The submitted `Dockerfile` is built and started, and only its HTTP behavior is exercised; it does not import or execute the submission's source files on the host that runs it.

### R1.20  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 37)
- Text:

> The image must run on its own with `-e PORT=<port>` and a port mapping.

### R1.21  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 37)
- Text:

> All runtime dependencies, initialization and seed data must work within that single container.

### R1.22  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment (spec line 37)
- Text:

> Compose configuration is not used to start the service.

### R1.23  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 43)
- Text:

> Two providers are available:

### R1.24  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 43)
- Text:

> `nimble` and `tavily`.

### R1.25  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 43)
- Text:

> Nimble is the default provider: every service must be able to research companies using Nimble alone.

### R1.26  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 43)
- Text:

> Tavily is optional: a service may use it beside Nimble, and its absence must not prevent research while Nimble answers.

### R1.27  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 43)
- Text:

> The live submission and optional live judging provide a working Nimble key only.

### R1.28  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 48)
- Text:

> The service reaches the providers only through WebRouter, the Python package `webrouter` (module `web_router`).

### R1.29  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 48)
- Text:

> The service may be written in any language, but every request to a provider goes through `web_router`: called in-process, or from a Python helper process that the service runs inside its own container.

### R1.30  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 48)
- Text:

> The stage folder's dependency manifest lists `webrouter>=0.12.0`.

### R1.31  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 48)
- Text:

> Calling a provider's API by any other route is not permitted.

### R1.32  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 48)
- Text:

> Install it and the provider SDK dependencies from PyPI, including in the service's Docker build:

### R1.33  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 55)
- Text:

> ```sh
> pip install "webrouter[search,extract,research]>=0.12.0"
> ```

### R1.34  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 60)
- Text:

> The deployment provides these environment variables:

### R1.35  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 64)
- Text:

> | `PORT` | The port to listen on (§3.1) |

### R1.36  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 65)
- Text:

> | `NIMBLE_API_KEY` | Credential for the `nimble` provider |

### R1.37  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 66)
- Text:

> | `NIMBLE_BASE_URL` | Base URL of the `nimble` provider endpoint |

### R1.38  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 67)
- Text:

> | `TAVILY_API_KEY` | Credential for the `tavily` provider |

### R1.39  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 68)
- Text:

> | `TAVILY_BASE_URL` | Base URL of the `tavily` provider endpoint |

### R1.40  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 70)
- Text:

> Keys are opaque non-empty strings.

### R1.41  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 70)
- Text:

> WebRouter's `nimble` provider reads `NIMBLE_API_KEY` and `NIMBLE_BASE_URL` from the environment, and its `tavily` provider reads `TAVILY_API_KEY`.

### R1.42  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 70)
- Text:

> A service that uses Tavily passes its base URL to WebRouter in `provider_config`:

### R1.43  [pkg PC] [accepted]
- Section: 2. Delivery and deployment / Web access (spec line 74)
- Text:

> ```python
> provider_config={"tavily": {"api_base_url": <TAVILY_BASE_URL>}}
> ```

### R1.44  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 80)
- Text:

> The service must operate within these limits:

### R1.45  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 84)
- Text:

> | CPU | 2 vCPU |

### R1.46  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 85)
- Text:

> | Memory | 3 GiB |

### R1.47  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 86)
- Text:

> | Start to first healthy response | 60 s |

### R1.48  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 87)
- Text:

> | Concurrent requests | up to 50 in flight |

### R1.49  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 88)
- Text:

> | Per-request timeout | 5 s (10 s for `POST /_test/reset`) |

### R1.50  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 89)
- Text:

> | Outbound network | available during `docker build`; at run time, **only the provider endpoints this specification lists** |

### R1.51  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 90)
- Text:

> | Disk | ephemeral; state need not survive a container restart |

### R1.52  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 92)
- Text:

> Runtime assets and dependencies must be included in the image.

### R1.53  [pkg PA1] [accepted]
- Section: 2. Delivery and deployment / Resource limits (spec line 92)
- Text:

> This includes fonts, scripts and stylesheets; external services other than the provider endpoints this specification lists are unavailable at runtime.

### R1.54  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.1 Listening (spec line 100)
- Text:

> Listen on `0.0.0.0` using the `PORT` environment variable, default `8080`.

### R1.55  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.2 Health (spec line 104)
- Text:

> ```http
> GET /health  ->  200  {"status": "ok"}
> ```

### R1.56  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.2 Health (spec line 108)
- Text:

> Return 200 once the service and its data store can serve requests, within 60 seconds of container start.

### R1.57  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.2 Health (spec line 108)
- Text:

> Non-200 responses are permitted before the service is ready.

### R1.58  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.2 Health (spec line 108)
- Text:

> `/health` makes no provider call.

### R1.59  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.3 Reset and seed (spec line 114)
- Text:

> ```http
> POST /_test/reset
> Content-Type: application/json
> 
> { ...fixture... }
> 
> ->  204 No Content
> ```

### R1.60  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.3 Reset and seed (spec line 123)
- Text:

> Replace all service state with the fixture in the request body (§4).

### R1.61  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.3 Reset and seed (spec line 123)
- Text:

> When reset returns 204, subsequent requests must see only that fixture: no users other than the seeded ones, no dossiers and no stored idempotent responses.

### R1.62  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.3 Reset and seed (spec line 123)
- Text:

> Repeated resets are supported.

### R1.63  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.3 Reset and seed (spec line 123)
- Text:

> A build still running when reset is called must not change the state that follows the reset.

### R1.64  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.3 Reset and seed (spec line 123)
- Text:

> This control endpoint must be enabled in the delivered image and requires no authentication.

### R1.65  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.4 Clock (spec line 131)
- Text:

> The service keeps a clock that only reset and `POST /_test/clock` move.

### R1.66  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.4 Clock (spec line 131)
- Text:

> Every timestamp the service records or returns is read from this clock.

### R1.67  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.4 Clock (spec line 134)
- Text:

> ```http
> POST /_test/clock
> Content-Type: application/json
> 
> { "now": "2026-03-01T09:30:00+00:00" }
> 
> ->  204 No Content
> ```

### R1.68  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.4 Clock (spec line 143)
- Text:

> - Reset sets the clock to the fixture's `now`. Before the first reset the clock follows the
>   system time.

### R1.69  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.4 Clock (spec line 145)
- Text:

> - The clock stands still between calls: two requests with no clock call between them read
>   the same time.

### R1.70  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.4 Clock (spec line 147)
- Text:

> - `now` is an RFC 3339 timestamp with an explicit offset. A `now` earlier than the clock's
>   current time is 422 `validation_failed` and changes nothing.

### R1.71  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.4 Clock (spec line 149)
- Text:

> - `POST /_test/clock` requires no authentication.

### R1.72  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.5 Conventions (spec line 153)
- Text:

> - Requests and responses are `application/json; charset=utf-8`.

### R1.73  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.5 Conventions (spec line 154)
- Text:

> - Timestamps in responses are RFC 3339 with an explicit offset, e.g. `2026-09-24T19:00:00+02:00`.

### R1.74  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.5 Conventions (spec line 155)
- Text:

> - Unknown fields in a request body are ignored, never an error.

### R1.75  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.5 Conventions (spec line 156)
- Text:

> - Unknown query parameters are ignored.

### R1.76  [pkg PA1] [accepted]
- Section: 3. Runtime contract / 3.5 Conventions (spec line 157)
- Text:

> - IDs are opaque strings of at most 64 characters. Their format is yours.

### R1.77  [pkg PA1] [accepted]
- Section: 4. Model / Users (spec line 163)
- Text:

> Users sign up and log in (§6).

### R1.78  [pkg PA1] [accepted]
- Section: 4. Model / Users (spec line 163)
- Text:

> Every authenticated user sees the same dossiers.

### R1.79  [pkg PA1] [accepted]
- Section: 4. Model / Domains (spec line 167)
- Text:

> A company is identified by its domain.

### R1.80  [pkg PA1] [accepted]
- Section: 4. Model / Domains (spec line 167)
- Text:

> Every domain the API takes, in a body or a path, is first **normalised**: surrounding whitespace removed, lowercased, one trailing `.` removed, and one leading `www.` removed.

### R1.81  [pkg PA1] [accepted]
- Section: 4. Model / Domains (spec line 167)
- Text:

> The normalised domain must then be a valid host name: two or more labels separated by `.`, each label 1 to 63 characters of `a-z`, `0-9` and `-`, not starting or ending with `-`, and 253 characters or fewer in total.

### R1.82  [pkg PA1] [accepted]
- Section: 4. Model / Domains (spec line 167)
- Text:

> Anything else, including a URL with a scheme or a path, is 422 `validation_failed`.

### R1.83  [pkg PA1] [accepted]
- Section: 4. Model / Domains (spec line 174)
- Text:

> `Acme-Robotics.TEST.`, `www.acme-robotics.test` and `acme-robotics.test` name the same company and the same dossier.

### R1.84  [pkg PA1] [accepted]
- Section: 4. Model / Domains (spec line 174)
- Text:

> Responses always carry the normalised domain.

### R1.85  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 179)
- Text:

> A dossier has exactly these six fields:

### R1.86  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 183)
- Text:

> | `legal_name` | String: the company's registered name, e.g. `Acme Robotics, Inc.` |

### R1.87  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 184)
- Text:

> | `hq_city` | String: the city of the company's headquarters, without region or country, e.g. `Lisbon` |

### R1.88  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 185)
- Text:

> | `ceo` | String: the full name of the company's chief executive, e.g. `Dana Ruiz` |

### R1.89  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 186)
- Text:

> | `founded_year` | Integer: the year the company was founded, e.g. `2014` |

### R1.90  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 187)
- Text:

> | `headcount_range` | String: one of `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+` |

### R1.91  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 188)
- Text:

> | `funding_total` | Integer: total equity funding raised, in whole US dollars, e.g. `12000000` |

### R1.92  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 190)
- Text:

> A string value is written as the supporting excerpt writes it, without surrounding whitespace.

### R1.93  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 190)
- Text:

> A headcount the web states as a number, or as a range that fits inside one of the ranges above, has the range that contains it as its value.

### R1.94  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 194)
- Text:

> Each field in a response has this shape:

### R1.95  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 196)
- Text:

> ```json
> { "value": "Dana Ruiz", "status": "known",
>   "citations": [ { "url": "https://acme-robotics.test/about",
>                    "excerpt": "Dana Ruiz has led Acme Robotics as chief executive since 2021.",
>                    "provider": "nimble" } ] }
> ```

### R1.96  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 203)
- Text:

> - `status` is `known` when `value` is not null, and `unknown` when it is.

### R1.97  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 204)
- Text:

> - A `known` field has one or more citations. An `unknown` field has `"value": null` and
>   `"citations": []`.

### R1.98  [pkg PB] [accepted]
- Section: 4. Model / Fields (spec line 206)
- Text:

> - `url` is the URL of the page the excerpt was served for, `provider` is `nimble` or
>   `tavily`, the provider that served it.

### R1.99  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 211)
- Text:

> The **evidence** for a company is every page that some search, through any provider and for any query naming the company (as in Appendix A.2), returns, with its full text, and every claim that a `nimble` research run for the company asking for all six fields answers with.

### R1.100  [pkg PC] [accepted]
- Section: 4. Model / Evidence and support (spec line 215)
- Text:

> Of the searches that a provider answers without an error, every build makes exactly one whose query is exactly the company's normalised domain, through a provider of its choice; its other such searches use other queries.

### R1.101  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 215)
- Text:

> A search that a provider answers with an error does not count.

### R1.102  [pkg PC] [accepted]
- Section: 4. Model / Evidence and support (spec line 215)
- Text:

> The pages whose text a build obtains from providers are the pages it **gathers**.

### R1.103  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 220)
- Text:

> A **citation** is an excerpt of text a provider served for the page at `url`:

### R1.104  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 222)
- Text:

> - The excerpt is copied character for character from that served text, except that any run
>   of whitespace may be written as a single space. It is 1 to 500 characters long.

### R1.105  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 224)
- Text:

> - It is taken from the page's prose (below), not from its header.

### R1.106  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 226)
- Text:

> An excerpt **supports** a value when, read on its own, it states that value for that field of this company, as Appendix A defines.

### R1.107  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 226)
- Text:

> The excerpt may write the value differently from the API:

### R1.108  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 226)
- Text:

> `Acme Robotics has raised $12M.` and `Acme Robotics has raised 12 million dollars.` both support a `funding_total` of `12000000`, and `Acme Robotics employs about 120 people.` supports a `headcount_range` of `51-200`.

### R1.109  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 232)
- Text:

> A research answer carries a claimed value for a field and a citation for the claim.

### R1.110  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 232)
- Text:

> The claim is asserted only when its citation supports it.

### R1.111  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 232)
- Text:

> A field is `unknown` when no evidence supports a value for it, even when a research answer claims one.

### R1.112  [pkg PB] [accepted]
- Section: 4. Model / Evidence and support (spec line 236)
- Text:

> When the evidence supports more than one value for a field, the field holds one of them and cites only excerpts that support that value.

### R1.113  [pkg PB] [accepted]
- Section: 4. Model / Pages (spec line 241)
- Text:

> Every page has a URL, a title and a text.

### R1.114  [pkg PB] [accepted]
- Section: 4. Model / Pages (spec line 241)
- Text:

> A text may begin with **header lines**, each of the form `Name: value`, where the name is a capitalised word or several joined by `-`.

### R1.115  [pkg PB] [accepted]
- Section: 4. Model / Pages (spec line 241)
- Text:

> The header ends at the first empty line; everything after it is the page's **prose**.

### R1.116  [pkg PB] [accepted]
- Section: 4. Model / Pages (spec line 241)
- Text:

> A text whose first line is not a header line has no header and is all prose.

### R1.117  [pkg PB] [accepted]
- Section: 4. Model / Pages (spec line 246)
- Text:

> The header line `Facts:` carries a JSON object on the same line.

### R1.118  [pkg PB] [accepted]
- Section: 4. Model / Pages (spec line 246)
- Text:

> Its keys are field names from the table above, and its values are what the page states for those fields, in any format.

### R1.119  [pkg PB] [accepted]
- Section: 4. Model / Pages (spec line 246)
- Text:

> It is informative only: citations come from the prose, and whether an excerpt supports a value is decided by Appendix A alone.

### R1.120  [pkg PB] [accepted]
- Section: 4. Model / Pages (spec line 246)
- Text:

> The service may ignore other header lines.

### R1.121  [pkg PA1] [accepted]
- Section: 4. Model / Fixture format (spec line 253)
- Text:

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

### R1.122  [pkg PA1] [accepted]
- Section: 4. Model / Fixture format (spec line 265)
- Text:

> - `now` is required and sets the clock (§3.4).

### R1.123  [pkg PA1] [accepted]
- Section: 4. Model / Fixture format (spec line 266)
- Text:

> - Seeded users must be able to log in with the given password immediately.

### R1.124  [pkg PA1] [accepted]
- Section: 4. Model / Fixture format (spec line 267)
- Text:

> - A fixture with two users sharing an email is a reset error: 422 `validation_failed`,
>   changing nothing.

### R1.125  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 272)
- Text:

> Every 4xx and 5xx response carries this body:

### R1.126  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 274)
- Text:

> ```json
> { "error": { "code": "not_found", "message": "human readable, any wording" } }
> ```

### R1.127  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 278)
- Text:

> Use the specified HTTP status and `code`.

### R1.128  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 278)
- Text:

> The human-readable `message` may use any wording.

### R1.129  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 278)
- Text:

> Endpoint-specific errors are listed with each endpoint.

### R1.130  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 283)
- Text:

> | 400 | `malformed_request` | Unparseable body, or a field of the wrong JSON type |

### R1.131  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 284)
- Text:

> | 400 | `missing_idempotency_key` | Required `Idempotency-Key` header absent or empty |

### R1.132  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 285)
- Text:

> | 401 | `unauthenticated` | Missing, malformed or unknown bearer token |

### R1.133  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 286)
- Text:

> | 404 | `not_found` | No such resource, or not visible to this caller |

### R1.134  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 287)
- Text:

> | 409 | `idempotency_key_reuse` | Key already used by this caller with a different request body |

### R1.135  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 288)
- Text:

> | 422 | `validation_failed` | A required field or query parameter is missing, or a stated rule is violated with no more specific code |

### R1.136  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 290)
- Text:

> A field of the correct JSON type with an invalid format or out-of-range value gives 422 `validation_failed`, unless an endpoint specifies a different error.

### R1.137  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 290)
- Text:

> In addition:

### R1.138  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 293)
- Text:

> - An integer-valued **query parameter** is written as plain decimal digits: `1e9`, `4.0` and `+4`
>   are 422 `validation_failed` whatever their numeric value.

### R1.139  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 295)
- Text:

> - Reserve 400 `malformed_request` for a body that does not parse or a field of the wrong type.

### R1.140  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 297)
- Text:

> Shared ranges, enforced on every endpoint that takes them:

### R1.141  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 301)
- Text:

> | `Idempotency-Key` | 1 to 255 characters | 422 `validation_failed` |

### R1.142  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 302)
- Text:

> | `limit` | integer 1 to 200 | 422 `validation_failed` |

### R1.143  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 303)
- Text:

> | `offset` | integer 0 or more | 422 `validation_failed` |

### R1.144  [pkg PA1] [accepted]
- Section: 5. Errors (spec line 305)
- Text:

> Requests must not produce 5xx responses, including under concurrent load and when a provider endpoint answers with an error.

### R1.145  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 310)
- Text:

> Authentication supports signup and login.

### R1.146  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 310)
- Text:

> Email verification, password reset, refresh tokens and role-management endpoints are out of scope.

### R1.147  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 313)
- Text:

> ```http
> POST /auth/signup
> { "email": "a@example.com", "password": "correct horse", "display_name": "Ada" }
> 
> ->  201  { "user_id": "u_1", "display_name": "Ada", "token": "..." }
> ```

### R1.148  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 320)
- Text:

> ```http
> POST /auth/login
> { "email": "a@example.com", "password": "correct horse" }
> 
> ->  200  { "user_id": "u_1", "display_name": "Ada", "token": "..." }
> ```

### R1.149  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 329)
- Text:

> | Email already registered | 409 `email_taken` |

### R1.150  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 330)
- Text:

> | Password shorter than 8 characters | 422 `validation_failed` |

### R1.151  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 331)
- Text:

> | `email` not of the form `local@domain` | 422 `validation_failed` |

### R1.152  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 332)
- Text:

> | `display_name` empty or longer than 100 characters | 422 `validation_failed` |

### R1.153  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 333)
- Text:

> | Wrong password or unknown email on login | 401 `unauthenticated` |

### R1.154  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 335)
- Text:

> For a user seeded by the fixture (§3.3), `user_id` is that user's `id` in the fixture.

### R1.155  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 337)
- Text:

> Every other endpoint requires a bearer token, except `/health`, the `/_test/*` endpoints and the two above.

### R1.156  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 337)
- Text:

> A request to such an endpoint that lacks a valid token is 401 `unauthenticated`, even when it also lacks a required `Idempotency-Key`.

### R1.157  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 341)
- Text:

> ```http
> Authorization: Bearer <token>
> ```

### R1.158  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 345)
- Text:

> Tokens do not expire.

### R1.159  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 345)
- Text:

> An account may have multiple valid tokens and concurrent sessions.

### R1.160  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 347)
- Text:

> Passwords must be stored using a password-hashing function such as bcrypt, scrypt or Argon2, or an equivalent.

### R1.161  [pkg PA1] [accepted]
- Section: 6. Authentication (spec line 347)
- Text:

> Plaintext password storage is not permitted.

### R1.162  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 352)
- Text:

> Two write paths require an idempotency key (§8): **`POST /dossiers`** and **`POST /dossiers/{domain}/refresh`**.

### R1.163  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 352)
- Text:

> Everything below applies to each of them independently.

### R1.164  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 356)
- Text:

> ```http
> Idempotency-Key: <client-chosen string, 1..255 characters>
> ```

### R1.165  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 360)
- Text:

> The key is scoped to **the authenticated user**.

### R1.166  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 360)
- Text:

> Two different users may use the same key string with no interaction between them.

### R1.167  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 363)
- Text:

> A replay means the same user sending the **same method, the same path and the same body**.

### R1.168  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 363)
- Text:

> The same key with the same body on a different path is a different request, not a replay, and must succeed normally.

### R1.169  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 363)
- Text:

> `Acme-Robotics.test` and `acme-robotics.test` in a path or body are different requests for this rule, though they name the same dossier.

### R1.170  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 370)
- Text:

> | Header absent or empty | 400 `missing_idempotency_key` |

### R1.171  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 371)
- Text:

> | First use of the key | The normal response (§8) |

### R1.172  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 372)
- Text:

> | Replay: same key, same body | **200**, body identical to the original response as a JSON value |

### R1.173  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 373)
- Text:

> | Same key, different body | 409 `idempotency_key_reuse` |

### R1.174  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 374)
- Text:

> | Key reused after the original request failed with 4xx | Treated as a first use |

### R1.175  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 376)
- Text:

> "Same body" means the same JSON value after parsing — key order and whitespace do not matter.

### R1.176  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 376)
- Text:

> Unknown fields are ignored (§3.5) and play no part in this comparison: a body that differs from the first only in unknown fields is the same body, so the request is a replay.

### R1.177  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 376)
- Text:

> `POST /dossiers/{domain}/refresh` takes no body; any body sent to it is ignored and plays no part in deciding a replay.

### R1.178  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 382)
- Text:

> For concurrent identical requests with an unused key, exactly one returns the normal response.

### R1.179  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 382)
- Text:

> The others return 200 with the same body.

### R1.180  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 382)
- Text:

> The operation takes effect only once.

### R1.181  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 385)
- Text:

> A successful replay returns the original response, even after the dossier has changed.

### R1.182  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 385)
- Text:

> It starts no build and makes no provider call.

### R1.183  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 388)
- Text:

> After the body has parsed as a JSON object and the caller is authenticated, an already claimed key is resolved before field validation.

### R1.184  [pkg PA2] [accepted]
- Section: 7. Idempotency (spec line 388)
- Text:

> Thus changing a successful request to an invalid body with the same key still returns `409 idempotency_key_reuse`.

### R1.185  [pkg PC] [accepted]
- Section: 8. API / Builds (spec line 396)
- Text:

> A **build** researches one dossier: it calls the providers, decides each field, and replaces the dossier's fields with the result when it completes.

### R1.186  [pkg PA2] [accepted]
- Section: 8. API / Builds (spec line 396)
- Text:

> A dossier's first build starts with `POST /dossiers`, and every later one with `POST /dossiers/{domain}/refresh`.

### R1.187  [pkg PA2] [accepted]
- Section: 8. API / Builds (spec line 396)
- Text:

> A build's **time** is the clock's time when the request that started it was received.

### R1.188  [pkg PA2] [accepted]
- Section: 8. API / Builds (spec line 401)
- Text:

> - A dossier has at most one build running at a time.

### R1.189  [pkg PC] [accepted]
- Section: 8. API / Builds (spec line 402)
- Text:

> - A build ends in `ready` when it completed, or `failed` when none of its provider calls
>   succeeded. A failed build leaves the fields as they were.

### R1.190  [pkg PC] [accepted]
- Section: 8. API / Builds (spec line 404)
- Text:

> - When a build completes `ready`, each field is `known` exactly when the evidence (§4)
>   supports a value for it.

### R1.191  [pkg PC] [accepted]
- Section: 8. API / Builds (spec line 406)
- Text:

> - A build whose provider calls each answer within one second ends within 10 seconds of the
>   request that started it.

### R1.192  [pkg PC] [accepted]
- Section: 8. API / Builds (spec line 408)
- Text:

> - That bound is not a deadline for slower providers. Against the live providers
>   (`NIMBLE_BASE_URL` unset, or its host `sdk.nimbleway.com`), where a Nimble search can take
>   over ten seconds and a research run about a minute, a build does not give up on a call
>   that has been waiting less than 30 seconds, nor stop gathering because of the time it has
>   run in its first 120 seconds. It still ends `ready` or `failed` within 300 seconds.

### R1.193  [pkg PC] [accepted]
- Section: 8. API / Builds (spec line 413)
- Text:

> - Reading a dossier, listing dossiers and every other request except `POST /dossiers` and
>   `POST /dossiers/{domain}/refresh` make no provider call.

### R1.194  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers` (spec line 418)
- Text:

> **An idempotent write path.** `Idempotency-Key` is required; see §7.

### R1.195  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers` (spec line 420)
- Text:

> ```http
> POST /dossiers
> Authorization: Bearer <token>
> Idempotency-Key: 2f9c1a...
> 
> { "domain": "acme-robotics.test" }
> ```

### R1.196  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers` (spec line 428)
- Text:

> ```json
> 202
> { "dossier_id": "d_7", "domain": "acme-robotics.test", "state": "building" }
> ```

### R1.197  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers` (spec line 433)
- Text:

> When no dossier exists for the domain, the service creates one, starts its first build and returns 202.

### R1.198  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers` (spec line 433)
- Text:

> When a dossier already exists for the domain, the service starts no build and returns **200** with that dossier's `dossier_id`, `domain` and current `state`.

### R1.199  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers` (spec line 437)
- Text:

> Concurrent requests for the same domain create one dossier and start one build, whatever their keys.

### R1.200  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers` (spec line 442)
- Text:

> | `domain` missing | 422 `validation_failed` |

### R1.201  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers` (spec line 443)
- Text:

> | `domain` invalid after normalisation (§4) | 422 `validation_failed` |

### R1.202  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers/{domain}` (spec line 447)
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

### R1.203  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers/{domain}` (spec line 465)
- Text:

> - `state` is `building` while a build runs, otherwise the outcome of the latest build,
>   `ready` or `failed`.

### R1.204  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers/{domain}` (spec line 467)
- Text:

> - `fields` always holds all six fields. Before the first build completes `ready`, every
>   field is `unknown`. While a later build runs, `fields` are those of the last build that
>   completed `ready`.

### R1.205  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers/{domain}` (spec line 470)
- Text:

> - `researched_at` is the time of the last build that completed `ready`, or null.

### R1.206  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers/{domain}` (spec line 471)
- Text:

> - `spent_units` is the total cost (§9) of every provider call made for this dossier, by
>   every build, since it was created.

### R1.207  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers/{domain}` (spec line 473)
- Text:

> - The domain in the path is normalised (§4). No dossier for it is 404 `not_found`.

### R1.208  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers/{domain}/refresh` (spec line 477)
- Text:

> **An idempotent write path.** `Idempotency-Key` is required; see §7.

### R1.209  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers/{domain}/refresh` (spec line 477)
- Text:

> No body.

### R1.210  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers/{domain}/refresh` (spec line 479)
- Text:

> Starts a new build of the dossier and returns 202 with `{ "dossier_id", "domain", "state": "building" }`.

### R1.211  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers/{domain}/refresh` (spec line 479)
- Text:

> A refresh received while a build of the dossier is running starts no second build and returns 202 with the same body.

### R1.212  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers/{domain}/refresh` (spec line 483)
- Text:

> A refresh researches again: its build makes provider calls whether or not anything has changed since the last build, and its spending counts in `spent_units`.

### R1.213  [pkg PA2] [accepted]
- Section: 8. API / `POST /dossiers/{domain}/refresh` (spec line 488)
- Text:

> | No dossier for the domain | 404 `not_found` |

### R1.214  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers` (spec line 492)
- Text:

> ```http
> GET /dossiers?q=acme&limit=50&offset=0
> ```

### R1.215  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers` (spec line 496)
- Text:

> ```json
> { "dossiers": [ { "dossier_id": "d_7", "domain": "acme-robotics.test", "state": "ready",
>                   "legal_name": "Acme Robotics, Inc.", "researched_at": "2026-03-01T09:00:00+00:00",
>                   "spent_units": 34 } ],
>   "has_more": false }
> ```

### R1.216  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers` (spec line 503)
- Text:

> - `legal_name` is the value of the dossier's `legal_name` field, or null.

### R1.217  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers` (spec line 504)
- Text:

> - `q` is optional. When present, only dossiers whose domain or `legal_name` contains `q`,
>   compared case-insensitively, are listed. An empty `q` lists every dossier.

### R1.218  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers` (spec line 506)
- Text:

> - Dossiers are ordered by domain ascending.

### R1.219  [pkg PA2] [accepted]
- Section: 8. API / `GET /dossiers` (spec line 507)
- Text:

> - `limit` defaults to 50, range 1 to 200. `offset` defaults to 0. `has_more` is true when
>   items exist beyond the last one returned.

### R1.220  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 512)
- Text:

> Each provider call has a cost in **units**:

### R1.221  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 516)
- Text:

> | Search through `nimble`, depth `lite` (title, URL and snippet) | 1 |

### R1.222  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 517)
- Text:

> | Search through `nimble`, depth `fast` (a truncated page body) | 5 |

### R1.223  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 518)
- Text:

> | Search through `nimble`, depth `deep` (the full page) | 15 |

### R1.224  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 519)
- Text:

> | Search through `tavily`, depth `lite` (title, URL and snippet) | 8 |

### R1.225  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 520)
- Text:

> | Search through `tavily`, depth `fast` (title, URL and a longer snippet) | 16 |

### R1.226  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 521)
- Text:

> | Search through `tavily`, depth `deep` (the full page) | 16 |

### R1.227  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 522)
- Text:

> | Extract through `nimble` | 1 per URL requested, including a URL for which no page is returned |

### R1.228  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 523)
- Text:

> | Extract through `tavily` | 2 per URL requested, including a URL for which no page is returned |

### R1.229  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 524)
- Text:

> | Research run through `nimble` | 25 when the run is started; checking on or collecting a run costs nothing |

### R1.230  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 526)
- Text:

> A search's depth is WebRouter's `search_depth`.

### R1.231  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 528)
- Text:

> A search returns at most 10 results, whatever number it asks for.

### R1.232  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 528)
- Text:

> A call that a provider refuses with an error status costs nothing.

### R1.233  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 528)
- Text:

> A call whose answer does not arrive, because it times out or its connection fails, costs its units as in the table, whether or not the provider received it.

### R1.234  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 528)
- Text:

> An extract that the provider answers with no page for the URL is not refused: it costs its units, as in the table, whatever status says so.

### R1.235  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 528)
- Text:

> An extract through `nimble` does not set `render`.

### R1.236  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 535)
- Text:

> A build stops making provider calls before its spending would exceed 80 units, and completes with the pages and research claims it has obtained.

### R1.237  [pkg PC] [accepted]
- Section: 9. Providers and cost (spec line 538)
- Text:

> A research request names the company by its domain in its query, and names the fields it asks for by the field names in §4, as the property names of its output schema.

### R1.238  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 543)
- Text:

> The service must support `GET /_test/export` and `POST /_test/import`.

### R1.239  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 543)
- Text:

> Like reset, these are unauthenticated control endpoints.

### R1.240  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 543)
- Text:

> Exports may contain credentials and session tokens; handle them as private artifacts.

### R1.241  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 543)
- Text:

> Return 200 from export with a JSON object containing `track: "dossier"`, `format_version: 1` and `state` (an implementation-defined JSON object).

### R1.242  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 543)
- Text:

> The state format is opaque to the caller and must be accepted unchanged by import.

### R1.243  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 550)
- Text:

> Import takes that entire object and atomically replaces the service's state, returning

### R1.244  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 551)
- Text:

> 204. It must accept an unchanged export produced by this service. No dependency on the
> source process, files, volume, port or network address is allowed. Import is replacement,
> not merge; repeating it restores the exported state without duplicating anything. Invalid
> JSON follows §5; missing fields, wrong track/version or an invalid state give 422
> `validation_failed` without changing the destination. These control calls have a 10-second
> timeout. Export is an atomic, read-only snapshot; subsequent source writes do not change it.

### R1.245  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 558)
- Text:

> Preserve accounts and hashed-password login, existing bearer tokens, dossiers with their ids, states, fields, citations, `researched_at` and `spent_units`, all completed idempotent request bodies and original responses.

### R1.246  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 558)
- Text:

> Identities and timestamps must not be regenerated.

### R1.247  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 558)
- Text:

> Import makes no provider call: imported dossiers are not researched again, and their citations remain citations served to this service.

### R1.248  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 558)
- Text:

> Failed request keys remain reusable.

### R1.249  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 558)
- Text:

> Existing tokens and retries must remain valid after import; replacing the state with a fresh fixture does not satisfy this requirement.

### R1.250  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 558)
- Text:

> Import removes all previous destination data and credentials.

### R1.251  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 558)
- Text:

> Reset clears all state, including imported state.

### R1.252  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 558)
- Text:

> Export and import do not change the clock.

### R1.253  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 558)
- Text:

> State need not survive an abrupt container restart.

### R1.254  [pkg PA2] [accepted]
- Section: 10. Export and import (spec line 568)
- Text:

> An export taken while a build is running holds the dossier as it was before that build; after import, that dossier is in the state of its last completed build, or `failed` with every field `unknown` when no build had completed.

### R1.255  [pkg PA2] [accepted]
- Section: 11. Concurrency (spec line 574)
- Text:

> Concurrent requests must produce the same results as executing them one at a time in some order.

### R1.256  [pkg PA2] [accepted]
- Section: 11. Concurrency (spec line 574)
- Text:

> The requirements above hold at every read.

### R1.257  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value (spec line 579)
- Text:

> This appendix is the whole definition of "supports" used in §4.

### R1.258  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value (spec line 579)
- Text:

> The service decides support by these rules alone.

### R1.259  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.1 Sentences (spec line 584)
- Text:

> A page's prose is split into lines at each line break, and each line into sentences.

### R1.260  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.1 Sentences (spec line 584)
- Text:

> A sentence ends after a `.`, `!` or `?`, together with any `"`, `”`, `’` or `)` directly after it, when whitespace follows.

### R1.261  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.1 Sentences (spec line 584)
- Text:

> A `.` that ends one of the legal-form suffixes in A.4, written as a whole word, does not end a sentence.

### R1.262  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.1 Sentences (spec line 584)
- Text:

> Each sentence is taken without its surrounding whitespace; empty sentences are dropped.

### R1.263  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.1 Sentences (spec line 590)
- Text:

> An excerpt is a **single sentence** when, with every run of whitespace written as one space, this rule splits it into exactly one sentence.

### R1.264  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 595)
- Text:

> An excerpt supports the value V for the field F of a company exactly when all of these hold:

### R1.265  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 597)
- Text:

> 1. It is a single sentence (A.1).

### R1.266  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 598)
- Text:

> 2. It names the company: it contains the company's normalised domain, or the company's
>    name. The company's name is the first label of its domain with each `-` read as a space:
>    `acme-robotics.test` is named by `Acme Robotics`.

### R1.267  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 601)
- Text:

> 3. It contains a statement phrase for F (A.3).

### R1.268  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 602)
- Text:

> 4. It contains none of the negating phrases (A.3).

### R1.269  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 603)
- Text:

> 5. It contains at least one value in F's format (A.4), and every value in F's format that it
>    contains normalises to V (A.5).

### R1.270  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 606)
- Text:

> The company's name, its domain and every phrase are matched without regard to case and as whole words: the characters directly before and after the match are not letters or digits.

### R1.271  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 606)
- Text:

> Phrases with a space match one space.

### R1.272  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 610)
- Text:

> For example, for `acme-robotics.test`:

### R1.273  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 614)
- Text:

> | `Dana Ruiz has led Acme Robotics as chief executive since 2021.` | `ceo` `Dana Ruiz` |

### R1.274  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 615)
- Text:

> | `Acme Robotics CEO: Sam Ortiz.` | `ceo` `Sam Ortiz` |

### R1.275  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 616)
- Text:

> | `Acme Robotics was founded in 2014.` | `founded_year` `2014` |

### R1.276  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 617)
- Text:

> | `Acme Robotics employs about 120 people.` | `headcount_range` `51-200` |

### R1.277  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 618)
- Text:

> | `Acme Robotics is reportedly in talks to raise $40M.` | nothing: a negating phrase |

### R1.278  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.2 The rule (spec line 619)
- Text:

> | `Acme Robotics opened a sales office in Porto.` | nothing: no statement phrase for `hq_city` |

### R1.279  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.3 Phrases (spec line 625)
- Text:

> | `legal_name` | `legal name`, `registered name`, `registered as`, `registered company`, `legal entity`, `name of record` |

### R1.280  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.3 Phrases (spec line 626)
- Text:

> | `hq_city` | `headquartered in`, `headquarters in`, `head office in`, `based in`, `registered office in`, `registered seat in` |

### R1.281  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.3 Phrases (spec line 627)
- Text:

> | `ceo` | `chief executive officer`, `chief executive`, `CEO` |

### R1.282  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.3 Phrases (spec line 628)
- Text:

> | `founded_year` | `founded`, `founding`, `established`, `incorporated` |

### R1.283  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.3 Phrases (spec line 629)
- Text:

> | `headcount_range` | `employs`, `employees`, `staff`, `people`, `headcount`, `workforce` |

### R1.284  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.3 Phrases (spec line 630)
- Text:

> | `funding_total` | `raised`, `funding`, `invested`, `investment` |

### R1.285  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.3 Phrases (spec line 632)
- Text:

> The negating phrases are:

### R1.286  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.3 Phrases (spec line 632)
- Text:

> `in talks to`, `plans to`, `planning to`, `wants to`, `expects to`, `hopes to`, `aims to`, `seeking`, `could`, `would`, `might`, `reportedly`, `rumoured`, `former`, `formerly`, `will become`, `not`.

### R1.287  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 638)
- Text:

> A **capitalised word** is an uppercase letter followed by one or more lowercase letters, with no letter or digit directly before or after it.

### R1.288  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 638)
- Text:

> The letters may be of any alphabet:

### R1.289  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 638)
- Text:

> `Zürich` and `Müller` are capitalised words.

### R1.290  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 638)
- Text:

> An **uppercase word** is two or more uppercase letters, with no letter or digit directly before or after it:

### R1.291  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 638)
- Text:

> `AI`, `USA`.

### R1.292  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 643)
- Text:

> A **number** is written in digits, optionally with a `,` before each group of three digits and a decimal part after a `.`:

### R1.293  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 643)
- Text:

> `120`, `1,200`, `12.5`, `12,000,000`.

### R1.294  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 643)
- Text:

> Digits directly next to a letter, or joined to other digits by `,` or `.` in any other way, are not a number.

### R1.295  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 649)
- Text:

> | `legal_name` | The company's name or its domain (matched as in A.2), then zero or more capitalised or uppercase words each after one space, then an optional `,`, one space, and a legal-form suffix with no letter or digit directly after it. Where several such texts start at the same place, the shortest counts |

### R1.296  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 650)
- Text:

> | `hq_city` | A place name directly after a statement phrase for `hq_city` and one space: the longest run of capitalised words joined by single spaces or by `-` that starts there, not part of a longer such run |

### R1.297  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 651)
- Text:

> | `ceo` | A person's name: a run of two or three capitalised words joined by single spaces that is not part of a longer such run. Occurrences of the company's name and of the statement phrases for `ceo` are first taken out of the sentence and separate the words around them |

### R1.298  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 652)
- Text:

> | `founded_year` | A number of exactly four digits, from 1800 to 2099, that is not part of an amount |

### R1.299  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 653)
- Text:

> | `headcount_range` | A number with no decimal part, 1 or more, that is not part of an amount. Words before it, such as `about` or `roughly`, do not change it. A stated range such as `51-200 employees` holds two numbers |

### R1.300  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 654)
- Text:

> | `funding_total` | An amount (below) |

### R1.301  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 656)
- Text:

> The legal-form suffixes, matched exactly as written here:

### R1.302  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 656)
- Text:

> `Inc.`, `Corp.`, `LLC`, `LLP`, `L.P.`, `Ltd`, `Limited`, `Pty Ltd`, `plc`, `PLC`, `GmbH`, `AG`, `KG`, `SE`, `AS`, `A/S`, `ASA`, `AB`, `Oy`, `Oyj`, `B.V.`, `N.V.`, `S.A.`, `S.A.S.`, `S.L.`, `S.r.l.`, `S.p.A.`, `s.r.o.`, `a.s.`, `K.K.`.

### R1.303  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 661)
- Text:

> An **amount** is written in one of these forms, matched without regard to case, with no letter or digit directly before it or after it:

### R1.304  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 664)
- Text:

> - `$`, `US$` or `USD`, an optional space, a number, and optionally a scale: `k`, `m`, `mn` or
>   `bn` directly after the number, or one space and `thousand`, `million` or `billion`.
>   Examples: `$12M`, `$12.5 million`, `US$12 million`, `USD 12 million`, `$12m`,
>   `$12,000,000`.

### R1.305  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 668)
- Text:

> - A number, optionally one space and `thousand`, `million` or `billion`, then one space and
>   `dollars` or `US dollars`. Examples: `12 million dollars`, `12,000,000 US dollars`.

### R1.306  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.4 Value formats (spec line 671)
- Text:

> Amounts in other currencies are not amounts.

### R1.307  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.5 Normalisation (spec line 677)
- Text:

> | `legal_name`, `hq_city`, `ceo` | The text as the excerpt writes it |

### R1.308  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.5 Normalisation (spec line 678)
- Text:

> | `founded_year` | The number as an integer |

### R1.309  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.5 Normalisation (spec line 679)
- Text:

> | `headcount_range` | The range of §4 that contains the number |

### R1.310  [pkg PB] [accepted]
- Section: Appendix A. When an excerpt supports a value / A.5 Normalisation (spec line 680)
- Text:

> | `funding_total` | The number times the scale (`k` and `thousand` 1,000; `m`, `mn` and `million` 1,000,000; `bn` and `billion` 1,000,000,000) in US dollars. An amount that does not come to a whole number of dollars is not a value |


## Status table (final)

| Pkg | Ledger scope | Status |
|---|---|---|
| PA1 | all `[pkg PA1]` | accepted (main 9c82b37) |
| PA2 / PA2b | all `[pkg PA2]` | accepted (main d0e400f, 5b2b7e7) |
| PB | all `[pkg PB]` | accepted after one rejection (main e5568ca) |
| PC | all `[pkg PC]` | accepted after two rejections (main f21751d) |
| ALL | R1.1–R1.4 (process rules) | accepted |

Counts at freeze: 310 entries, 310 accepted, 0 open, 0 built, 0 tested. R1.42–R1.43 (optional Tavily use) are accepted as satisfied by a Nimble-only service (R1.25 allows it). R1.253 (restart) and R1.192 (live-provider timing) are structural/permission statements; R1.192 is covered by the mock delay-fault test.

## Rulings added during the stage

- **Rul-11 (amends Rul-2).** `run_build(domain, on_spend=None)`; `on_spend(+units)` on reservation, `on_spend(-units)` on release of an error-refused call; `BuildOutcome.spent_units` equals the net. Dossier `spent_units` is a live counter.
- **Rul-12 (R1.257, A.1).** Only a "." belonging to a suffix written with its own dot (Inc., Corp., L.P., B.V., N.V., S.A., S.A.S., S.L., S.r.l., S.p.A., s.r.o., a.s., K.K.) is exempt from ending a sentence; `Ltd.`, `AS.`, `PLC.` end a sentence.
- **Rul-13.** `excerpt_in_prose` stays strict about leading/trailing whitespace (service only emits trimmed single-sentence excerpts).
- **Rul-14.** R1.253 is a permission (no test); R1.192 is tested only through mock delay faults.

## Rejections (stage 1)

| Item | Commit | Reason | Change |
|---|---|---|---|
| PB | 2bc5260 | R1.257: `_ends_with_suffix` also exempted "." after suffixes written without a dot (Ltd., AS., ...) | Fixed per Rul-12; ceo A.4 character-before check added; PD2 tests added |
| PC | ac61e08 | `run_build` lacked `on_spend` (Rul-11); `app/research.py` did not re-export FIELD_NAMES/FieldResult/unknown_fields/BuildOutcome; not rebased on main | Re-based, re-exported, signature fixed |
| PC | 7588c1b / bdb841b | Same integration gaps (branch not on current main; FIELD_NAMES missing) | Handed off alone on main e5568ca as e4e62c2 → accepted |

## Frozen

Stage 1 frozen at main 34d96762f8e798683d97b9ca5195ad808175cd37 (merge of PT delay test, containing PA1, PA2, PA2b, PB, PC, PD, PD2 and the acceptance suite).
Final checks: full acceptance suite 178 passed / 0 failed; unit 244 passed; service tests 29 OK; event check stage 1 pass non-isolated (checks/s1-1) and isolated (checks/s1-final).
Known open risks: the Prover's step-7 defect-planting found 3 defects the suite does not catch (80-unit cap not forced, unverified research citations, negating phrase on a served page); tests for them are to be added in the next stage's folder. No live Nimble run was possible.
Stage 1 started 2026-11-21T05:08Z; frozen 2026-11-21T05:44Z.


---

# Stage 2 (started 2026-11-21T05:47Z) — competing sources and the dossier screens

Stage-1 entries above stay in force (cumulative; all accepted at the stage-1 freeze, main 34d9676). Stage 2 entries are `R2.*`.

## Packages (stage 2)

| Pkg | Owner | Scope | Order |
|---|---|---|---|
| R2S | @builder-a | `app/candidates.py` (the `Candidate` dataclass), `app/selection.py` (pure selection rule, status, ordering), dossier model/API changes (fields gain `candidates`, `status` known/contested/unknown, `value`/`citations` from selection, `retrieved_at` = build time, `GET /dossiers` legal_name = selected), export/import v2 including accepting a stage-1 export (derive candidates, keep tokens/idempotency), content negotiation hook for `Accept: text/html` on `/dossiers/{domain}` (route table only; UI owned by R2U1) | first |
| R2R | @builder-b | research changes: all candidates (every supported value on every gathered page, one candidate per page and excerpt), research-cited pages gathered and read like any other, page kind and `Published` parsing (`app/pages.py`), 429 handling (retry after >= 1 s, waiting does not count toward the 10 s bound, still <= 80 units, no cost on 429), optional Nimble rendered extract (3 units) and optional browser vendors (not required), page text = browser text | first (parallel with R2S) |
| R2U1 | @builder-b | UI: routes `/`, `/dossiers/{domain}`, `/signup`, `/login`, shared layout/design system/navigation, auth flow, research and refresh with uncertain-outcome handling, polling while building, latest-read-wins, 375 px responsive; every `data-testid` in the spec | after R2R |
| R2U2 | @builder-a | UI: `/dossiers/{domain}/evidence` and `/contested` screens and their testids, using the R2U1 layout; later joint visual polish and the 375 px review | after R2S, on top of R2U1's shared layout once merged |
| PT2 | @prover | Stage-2 acceptance tests: API (candidates, selection rule oracle, status, import of a stage-1 export, rate limits via mock faults) and browser tests with the data-testids (Playwright) at 375 px and desktop; also the 3 stage-1 gaps (80-unit cap forced, unverified research citation, negating phrase on a served page) in stage-2/tests/acceptance | in parallel from the start |
| GK | @gatekeeper | review/merge/checks | as packages land |

## Rulings (stage 2)

- **Rul-S2-1 (shapes between packages).** `app/candidates.py` defines `@dataclass(frozen=True) Candidate(value, url, excerpt, provider, kind, published_at)` where `value` is the normalised value (str or int), `kind` is `own|filing|news|aggregator` (or None only for an imported candidate), `published_at` an RFC 3339 string with offset or None. `app/research.py`'s `run_build(domain, on_spend=None)` now returns `BuildOutcome(ok, spent_units, candidates: dict[str, list[Candidate]])` (all six field names as keys, each a list, deduplicated on (value, url, excerpt, provider)). `app/selection.py` (R2S) turns the lists into the API `fields` (value/status/citations/candidates with `selected` and `retrieved_at`). `FieldResult`/`unknown_fields` stay importable, because the stage-1 code paths use them; R2S owns their evolution.
- **Rul-S2-2 (stage-1 export import).** The frozen stage-1 export state does not record served page texts, only the dossier fields with their citations, so an imported dossier gets exactly one candidate per exported citation (value = the field's exported value; excerpt, url and provider from the citation; kind/published_at from the exported state when it records them, else null; `retrieved_at` = the dossier's `researched_at`), each candidate's value checked with `supported_values` when the field is known. Fields, status, citations then derive via the selection rule. A stage-2 export (format_version stays 1, `state` carries the candidates and `schema` marker) must also import. Tokens, hashed passwords, idempotency records, ids and timestamps are preserved exactly; an idempotent replay of a stage-1 request after import returns the original response.
- **Rul-S2-3 (page kind).** `Kind` header value matched exactly (case-sensitive) to `own|filing|news|aggregator`; otherwise the host rule from the spec. `Published` must parse as RFC 3339 with an explicit offset (a `Z` suffix is an offset); otherwise None. `published_at` is emitted as given by the page normalised to `+00:00`/the page's offset isoformat (preserve the value's instant; compare by instant).
- **Rul-S2-4 (render).** Plain Nimble extract (1 unit) remains the default page-text source; the mock serves the same text as a render. Do not use `render` unless a ledger requirement fails without it. Kernel/Browserbase are not used.
- **Rul-S2-5 (429).** A call answered 429 costs 0 and is released from the budget ledger. Retry after waiting at least 1.05 s since that 429 (same call), up to the point where the budget or the 300 s limit would be exceeded; time spent waiting does not count toward the 10 s target, so the build's non-waiting work must still finish promptly. Give up on a call only after 4 consecutive 429s' worth of attempts has been made or the global deadline nears. Never let a 429 cause a 5xx or a failed build when other calls succeeded.
- **Rul-S2-6 (UI tech).** The UI is served by the same Python process with no runtime network use: server-rendered HTML with a small vanilla-JS enhancement layer and a local CSS file (no CDN, no fonts from the web, everything inside the image). Browser tests are run against `Accept: text/html` on the shared `/dossiers/{domain}` route; a request without that header gets JSON. The token is stored in `localStorage` (so a signed-in browser stays signed in after an export/import upgrade); `current-user` appears on every screen when signed in.
- **Rul-S2-7 (uncertain outcomes).** When a research/refresh request fails at the network level (no response), keep the key and body, show `research-uncertain`/`refresh-uncertain`, and a retry sends the same `Idempotency-Key` and body; success removes error and uncertain markers.

## Requirements (spec stage-2.md; every quote is verbatim; status: open | built | tested | accepted)

### R2.1  [pkg ALL] [open]
- Section: Dossier — Stage 2: competing sources and the dossier screens (spec line 3)
- Text:

> The stage-1 requirements continue to apply, with the additions below.

### R2.2  [pkg ALL] [open]
- Section: Dossier — Stage 2: competing sources and the dossier screens (spec line 3)
- Text:

> Numbered section references such as §4 and §7 refer to `stage-1.md`.

### R2.3  [pkg ALL] [open]
- Section: Dossier — Stage 2: competing sources and the dossier screens (spec line 6)
- Text:

> Sources disagree.

### R2.4  [pkg ALL] [open]
- Section: Dossier — Stage 2: competing sources and the dossier screens (spec line 6)
- Text:

> A dossier now keeps every value its evidence supports, as candidates, and selects one per field by a fixed rule.

### R2.5  [pkg ALL] [open]
- Section: Dossier — Stage 2: competing sources and the dossier screens (spec line 6)
- Text:

> Researchers read dossiers, their evidence and the fields in dispute in a browser.

### R2.6  [pkg ALL] [open]
- Section: Dossier — Stage 2: competing sources and the dossier screens (spec line 10)
- Text:

> The following applies to all operations, in addition to the stage-1 list:

### R2.7  [pkg ALL] [open]
- Section: Dossier — Stage 2: competing sources and the dossier screens (spec line 12)
- Text:

> 3. A field's selected value is the one the selection rule below picks from the field's
>    candidates; the same candidates always yield the same value.

### R2.8  [pkg R2R] [open]
- Section: Page kind and publication time (spec line 17)
- Text:

> Two header lines (§4, Pages) now carry requirements:

### R2.9  [pkg R2R] [open]
- Section: Page kind and publication time (spec line 21)
- Text:

> | `Kind: own`, `Kind: filing`, `Kind: news`, `Kind: aggregator` | The page's **kind**: the company's own site, a filing registry, a news report, or an aggregator of company data |

### R2.10  [pkg R2R] [open]
- Section: Page kind and publication time (spec line 22)
- Text:

> | `Published: <RFC 3339 timestamp>` | When the page was published |

### R2.11  [pkg R2R] [open]
- Section: Page kind and publication time (spec line 24)
- Text:

> A page with no `Kind` line, or with a value not listed above, is of kind `own` when the host of its URL, normalised as `stage-1.md` normalises a domain, is the company's domain, and of kind `aggregator` otherwise.

### R2.12  [pkg R2R] [open]
- Section: Page kind and publication time (spec line 24)
- Text:

> A page with no `Published` line, or with a value that is not an RFC 3339 timestamp, has no publication time.

### R2.13  [pkg R2R] [open]
- Section: Page text (spec line 31)
- Text:

> From this stage, a page's **text** is the text a browser shows once the page has loaded, without clicking controls.

### R2.14  [pkg R2R] [open]
- Section: Page text (spec line 31)
- Text:

> Activating disclosure controls is not required.

### R2.15  [pkg R2R] [open]
- Section: Page text (spec line 31)
- Text:

> The graded corpus contains no facts that require a click to reveal them.

### R2.16  [pkg R2R] [open]
- Section: Page text (spec line 31)
- Text:

> Evidence (§4) is read from page text so defined, and a citation's excerpt must appear in the page's text.

### R2.17  [pkg R2R] [open]
- Section: Page text (spec line 31)
- Text:

> A citation's `provider` is the provider that served the text the excerpt was copied from.

### R2.18  [pkg R2R] [open]
- Section: Web access (spec line 40)
- Text:

> From this stage an extract through `nimble` may ask Nimble to load the page in a browser and serve the text the browser shows once the page has loaded, with no control activated:

### R2.19  [pkg R2R] [open]
- Section: Web access (spec line 40)
- Text:

> `provider_options={"render":

### R2.20  [pkg R2R] [open]
- Section: Web access (spec line 40)
- Text:

> True}` on WebRouter's extract.

### R2.21  [pkg R2R] [open]
- Section: Web access (spec line 44)
- Text:

> Two optional browser vendors are also available, in addition to the providers in §2:

### R2.22  [pkg R2R] [open]
- Section: Web access (spec line 46)
- Text:

> - `kernel`, through `open_browser`;

### R2.23  [pkg R2R] [open]
- Section: Web access (spec line 47)
- Text:

> - `browserbase`, through `open_browser` and `browse`.

### R2.24  [pkg R2R] [open]
- Section: Web access (spec line 49)
- Text:

> A service may use Nimble's rendered extract alone to obtain every page's browser text; neither browser vendor is required.

### R2.25  [pkg R2R] [open]
- Section: Web access (spec line 52)
- Text:

> The deployment provides these environment variables in addition to those in §2:

### R2.26  [pkg R2R] [open]
- Section: Web access (spec line 56)
- Text:

> | `KERNEL_API_KEY` | Credential for the `kernel` provider |

### R2.27  [pkg R2R] [open]
- Section: Web access (spec line 57)
- Text:

> | `KERNEL_BASE_URL` | Base URL of the `kernel` provider endpoint |

### R2.28  [pkg R2R] [open]
- Section: Web access (spec line 58)
- Text:

> | `BROWSERBASE_API_KEY` | Credential for the `browserbase` provider |

### R2.29  [pkg R2R] [open]
- Section: Web access (spec line 59)
- Text:

> | `BROWSERBASE_BASE_URL` | Base URL of the `browserbase` provider endpoint |

### R2.30  [pkg R2R] [open]
- Section: Web access (spec line 61)
- Text:

> WebRouter reads the keys from the environment.

### R2.31  [pkg R2R] [open]
- Section: Web access (spec line 61)
- Text:

> A service that uses these vendors passes their base URLs to WebRouter in `provider_config`, beside those of §2:

### R2.32  [pkg R2R] [open]
- Section: Web access (spec line 64)
- Text:

> ```python
> provider_config={"kernel": {"base_url": <KERNEL_BASE_URL>},
>                  "browserbase": {"base_url": <BROWSERBASE_BASE_URL>}}
> ```

### R2.33  [pkg R2R] [open]
- Section: Web access (spec line 69)
- Text:

> These calls cost, in the units of §9:

### R2.34  [pkg R2R] [open]
- Section: Web access (spec line 73)
- Text:

> | Extract through `nimble` that loads the page in a browser | 3 per URL requested, including a URL for which no page is returned |

### R2.35  [pkg R2R] [open]
- Section: Web access (spec line 74)
- Text:

> | Open a session through `kernel` | 0 |

### R2.36  [pkg R2R] [open]
- Section: Web access (spec line 75)
- Text:

> | Open a session through `browserbase` | 2 |

### R2.37  [pkg R2R] [open]
- Section: Web access (spec line 76)
- Text:

> | Each page served to a session, through either | 1 |

### R2.38  [pkg R2R] [open]
- Section: Web access (spec line 77)
- Text:

> | Browse run through `browserbase` | 4 |

### R2.39  [pkg R2R] [open]
- Section: Web access (spec line 79)
- Text:

> A failed open, a failed page load and releasing a session cost nothing.

### R2.40  [pkg R2R] [open]
- Section: Web access (spec line 81)
- Text:

> Each provider keeps at most 4 sessions open at once; opening another is answered with an error.

### R2.41  [pkg R2R] [open]
- Section: Web access (spec line 81)
- Text:

> A session that no client has been connected to for 60 seconds is closed by the provider.

### R2.42  [pkg R2R] [open]
- Section: Rate limits (spec line 87)
- Text:

> From this stage a provider may answer any call with 429.

### R2.43  [pkg R2R] [open]
- Section: Rate limits (spec line 87)
- Text:

> A call answered 429 costs nothing (`stage-1.md` §9).

### R2.44  [pkg R2R] [open]
- Section: Rate limits (spec line 87)
- Text:

> The same call (the same provider, operation and arguments) made again less than one second after a 429 for it was answered is answered 429 again.

### R2.45  [pkg R2R] [open]
- Section: Rate limits (spec line 87)
- Text:

> No call is answered 429 more than three times in a row, except that opening a session while its provider keeps 4 open (Web access) is answered 429 until one of them closes.

### R2.46  [pkg R2R] [open]
- Section: Rate limits (spec line 87)
- Text:

> Time a build spends waiting to make a call again after a 429 does not count toward the 10 seconds of `stage-1.md` §8.

### R2.47  [pkg R2S] [open]
- Section: Candidates (spec line 96)
- Text:

> A **candidate** is one value for one field, supported by one excerpt of one page.

### R2.48  [pkg R2R] [open]
- Section: Candidates (spec line 96)
- Text:

> Every value that a page of the evidence (§4) supports for a field is a candidate of that field, once for each such page.

### R2.49  [pkg R2R] [open]
- Section: Candidates (spec line 96)
- Text:

> The evidence now also holds the page that each research claim of the evidence cites, whether or not the citation supports its claim: a build reads that page as it reads any other.

### R2.50  [pkg R2R] [open]
- Section: Candidates (spec line 96)
- Text:

> A research claim whose citation does not support it is still not a candidate.

### R2.51  [pkg R2R] [open]
- Section: Candidates (spec line 96)
- Text:

> A candidate's `provider` is a provider that served the text its excerpt is taken from; when several did, any of them may be given.

### R2.52  [pkg R2S] [open]
- Section: Candidates (spec line 104)
- Text:

> Each field gains `candidates`:

### R2.53  [pkg R2R] [open]
- Section: Candidates (spec line 106)
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

### R2.54  [pkg R2R] [open]
- Section: Candidates (spec line 126)
- Text:

> - `url`, `excerpt` and `provider` follow the citation rules in §4.

### R2.55  [pkg R2S] [open]
- Section: Candidates (spec line 127)
- Text:

> - `kind` is the page's kind, and `published_at` its publication time or null. Only an
>   imported candidate (below) has a null `kind`; it has the authority of `aggregator`.

### R2.56  [pkg R2R] [open]
- Section: Candidates (spec line 129)
- Text:

> - `retrieved_at` is the time of the build that gathered the candidate (§8, Builds).

### R2.57  [pkg R2S] [open]
- Section: Candidates (spec line 130)
- Text:

> - `selected` is true on exactly one candidate of a field that has candidates, the one the
>   rule picks, and false on the others.

### R2.58  [pkg R2S] [open]
- Section: Candidates (spec line 132)
- Text:

> - `candidates` lists the candidates of the last build that completed `ready`, in the order
>   the selection rule ranks them, the selected one first. A field with no candidate has
>   `"candidates": []` and is `unknown`.

### R2.59  [pkg R2S] [open]
- Section: Candidates (spec line 135)
- Text:

> - Two values are the same value when they are equal as JSON values; strings are compared
>   exactly, after removing surrounding whitespace.

### R2.60  [pkg R2S] [open]
- Section: The selection rule (spec line 140)
- Text:

> Rank a field's candidates, highest first, by:

### R2.61  [pkg R2S] [open]
- Section: The selection rule (spec line 142)
- Text:

> 1. **Authority** of the page's kind: `own` and `filing` rank equal and highest, then `news`,
>    then `aggregator`.

### R2.62  [pkg R2S] [open]
- Section: The selection rule (spec line 144)
- Text:

> 2. **Recency** within the same authority: the later `published_at` ranks higher. A candidate
>    without a publication time ranks below every candidate of the same authority that has one.

### R2.63  [pkg R2S] [open]
- Section: The selection rule (spec line 146)
- Text:

> 3. **URL**: when authority and publication time are equal, the candidate whose `url` is
>    smaller, comparing the strings by Unicode code point, ranks higher; between two
>    candidates with the same URL, they rank by provider in the order `nimble`, `tavily`,
>    `kernel`, `browserbase`.

### R2.64  [pkg R2S] [open]
- Section: The selection rule (spec line 150)
- Text:

> 4. **Value**: between two candidates with the same URL and provider, the one whose value is
>    smaller ranks higher: integers compare as numbers, strings by Unicode code point after
>    removing surrounding whitespace.

### R2.65  [pkg R2S] [open]
- Section: The selection rule (spec line 154)
- Text:

> The highest-ranked candidate is the selected one.

### R2.66  [pkg R2S] [open]
- Section: The selection rule (spec line 154)
- Text:

> The field's `value` is the selected candidate's value, and its `citations` are the `url`, `excerpt` and `provider` of every candidate with that value, in rank order.

### R2.67  [pkg R2S] [open]
- Section: The selection rule (spec line 158)
- Text:

> A candidate of lower authority is selected only when no candidate of higher authority exists for that field.

### R2.68  [pkg R2S] [open]
- Section: The selection rule (spec line 158)
- Text:

> The rule runs over all of a field's candidates.

### R2.69  [pkg R2S] [open]
- Section: Status (spec line 163)
- Text:

> `status` is now one of three values:

### R2.70  [pkg R2S] [open]
- Section: Status (spec line 167)
- Text:

> | `known` | The field has candidates, and they all have the same value |

### R2.71  [pkg R2S] [open]
- Section: Status (spec line 168)
- Text:

> | `contested` | The field's candidates carry two or more different values |

### R2.72  [pkg R2S] [open]
- Section: Status (spec line 169)
- Text:

> | `unknown` | The field has no candidate; `value` is null |

### R2.73  [pkg R2S] [open]
- Section: Status (spec line 171)
- Text:

> A `contested` field still has a selected `value` and its citations.

### R2.74  [pkg R2S] [open]
- Section: Status (spec line 173)
- Text:

> `GET /dossiers` (§8) is unchanged.

### R2.75  [pkg R2S] [open]
- Section: Status (spec line 173)
- Text:

> The `legal_name` it lists is the selected value.

### R2.76  [pkg R2U1] [open]
- Section: Screens (spec line 177)
- Text:

> The following screens must be reachable by URL.

### R2.77  [pkg R2U1] [open]
- Section: Screens (spec line 177)
- Text:

> Other screens must be reachable through the UI.

### R2.78  [pkg R2U1] [open]
- Section: Screens (spec line 177)
- Text:

> Server-side and client-side rendering are both permitted.

### R2.79  [pkg R2U1] [open]
- Section: Screens (spec line 182)
- Text:

> | `/` | The dossier list with search, and a form to research a domain |

### R2.80  [pkg R2U1] [open]
- Section: Screens (spec line 183)
- Text:

> | `/dossiers/{domain}` | One dossier: its state, its six fields with their values, status and citations, a refresh and a reload |

### R2.81  [pkg R2U1] [open]
- Section: Screens (spec line 184)
- Text:

> | `/dossiers/{domain}/evidence` | Every candidate of every field of that dossier |

### R2.82  [pkg R2U1] [open]
- Section: Screens (spec line 185)
- Text:

> | `/contested` | Every contested field across all dossiers |

### R2.83  [pkg R2U1] [open]
- Section: Screens (spec line 186)
- Text:

> | `/signup` | Signup |

### R2.84  [pkg R2U1] [open]
- Section: Screens (spec line 187)
- Text:

> | `/login` | Login |

### R2.85  [pkg R2U1] [open]
- Section: Screens (spec line 189)
- Text:

> The browser and the API share `/dossiers/{domain}`.

### R2.86  [pkg R2U1] [open]
- Section: Screens (spec line 189)
- Text:

> Return the UI for `Accept: text/html`; API requests without that header receive JSON.

### R2.87  [pkg R2U1] [open]
- Section: Screens (spec line 189)
- Text:

> `/`, `/dossiers/{domain}/evidence` and `/contested` are browser routes; they read the API's dossier data.

### R2.88  [pkg R2U1] [open]
- Section: Screens (spec line 189)
- Text:

> The domain in a browser route is normalised as in §4.

### R2.89  [pkg R2U1] [open]
- Section: Screens (spec line 194)
- Text:

> The UI must expose the `data-testid` attributes listed below for integration testing.

### R2.90  [pkg R2U1] [open]
- Section: Screens (spec line 194)
- Text:

> Additional elements are permitted, and the visual implementation is the team's choice subject to the product-quality requirements below.

### R2.91  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 200)
- Text:

> The browser experience must feel like a coherent, presentation-ready research product, not a thin wrapper of raw controls.

### R2.92  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 200)
- Text:

> Aim for a calm, legible, evidence-first character: a reader opening a dossier should see at a glance which fields are known, which are unknown and which are contested, and where each value came from.

### R2.93  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 205)
- Text:

> A field's value and its status must be the clearest information on the dossier screen, with its citations directly beside it.

### R2.94  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 205)
- Text:

> Fields, citations, candidates and contested fields should be easy to scan, and status, provider, page kind and publication time should be understandable without interpreting raw API data.

### R2.95  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 205)
- Text:

> Use a consistent visual system for typography, spacing, colour, controls and feedback.

### R2.96  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 205)
- Text:

> Primary actions — research, refresh — must be easy to identify.

### R2.97  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 205)
- Text:

> Known, unknown, contested, building, failed, loading, successful, refused and uncertain states must be visually distinct as well as satisfying the behavioural requirements below.

### R2.98  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 205)
- Text:

> Format names, years, headcount ranges, money and timestamps for people first; expose technical identifiers only where they help the user.

### R2.99  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 205)
- Text:

> Each citation shows its excerpt as quoted text and links to its URL.

### R2.100  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 216)
- Text:

> The required flows must remain clear and usable at a 375 CSS-pixel viewport and at conventional desktop widths, without horizontal page scrolling.

### R2.101  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 216)
- Text:

> Inputs need visible labels, keyboard focus must be apparent, and text and controls need sufficient contrast.

### R2.102  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 216)
- Text:

> Provide considered empty, loading and error states, and keep navigation consistent across the required routes.

### R2.103  [pkg R2U1] [open]
- Section: Product and visual direction (spec line 216)
- Text:

> A custom illustration, brand asset or exact visual match to a reference is not required.

### R2.104  [pkg R2U1] [open]
- Section: Signup and login (spec line 226)
- Text:

> | `signup-email`, `signup-password`, `signup-display-name` | Inputs |

### R2.105  [pkg R2U1] [open]
- Section: Signup and login (spec line 227)
- Text:

> | `signup-submit` | Button |

### R2.106  [pkg R2U1] [open]
- Section: Signup and login (spec line 228)
- Text:

> | `login-email`, `login-password`, `login-submit` | Inputs and button |

### R2.107  [pkg R2U1] [open]
- Section: Signup and login (spec line 229)
- Text:

> | `auth-error` | Error message. Present only when there is one |

### R2.108  [pkg R2U1] [open]
- Section: Signup and login (spec line 230)
- Text:

> | `current-user` | Visible on every screen when signed in. Text contains the display name |

### R2.109  [pkg R2U1] [open]
- Section: Signup and login (spec line 231)
- Text:

> | `logout-button` | Button |

### R2.110  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 237)
- Text:

> | `research-domain` | Input for the domain to research |

### R2.111  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 238)
- Text:

> | `research-submit` | Button. Sends `POST /dossiers` |

### R2.112  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 239)
- Text:

> | `research-error` | Error message, when the request is refused — including an invalid domain |

### R2.113  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 240)
- Text:

> | `research-uncertain` | Shown when the outcome of a research request is unknown (below) |

### R2.114  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 241)
- Text:

> | `dossier-search` | Input. Filters the list as `q` does on `GET /dossiers` |

### R2.115  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 242)
- Text:

> | `dossier-list` | Container. Children ordered by domain ascending |

### R2.116  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 243)
- Text:

> | `dossier-item-{domain}` | One per listed dossier. Carries `data-state="{state}"`. Text contains the domain, and the legal name when known. Links to `/dossiers/{domain}` |

### R2.117  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 244)
- Text:

> | `empty-dossiers` | Shown instead of the list when no dossier matches |

### R2.118  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 246)
- Text:

> A research request that succeeds, with 202 or 200, opens `/dossiers/{domain}` for the normalised domain.

### R2.119  [pkg ALL] [open]
- Section: Dossier list — `/` (spec line 246)
- Text:

> A domain that already has a dossier, including one created by another client after this browser read the list, opens that dossier and starts no build.

### R2.120  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 254)
- Text:

> | `dossier-domain` | Text is exactly the normalised domain |

### R2.121  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 255)
- Text:

> | `dossier-state` | Text is exactly `building`, `ready` or `failed` |

### R2.122  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 256)
- Text:

> | `dossier-spent` | Formatted `spent_units`. Carries `data-units="{integer}"` |

### R2.123  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 257)
- Text:

> | `dossier-researched-at` | Text contains `researched_at`, formatted. Absent when it is null |

### R2.124  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 258)
- Text:

> | `field-{field}` | One per field, six in all, in the order of the table in `stage-1.md` §4. Carries `data-status="{status}"` |

### R2.125  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 259)
- Text:

> | `field-value-{field}` | The formatted value. Carries `data-value` (below). Present only when the value is not null |

### R2.126  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 260)
- Text:

> | `field-contested-{field}` | A marker. Present only when the field is `contested` |

### R2.127  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 261)
- Text:

> | `field-citations-{field}` | Container of the field's citations, in API order |

### R2.128  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 262)
- Text:

> | `citation-{field}-{n}` | The field's `n`th citation, counting from 1. Text contains the excerpt. Contains a link whose `href` is the citation's `url`. Carries `data-provider="{provider}"` |

### R2.129  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 263)
- Text:

> | `dossier-evidence-link` | Link to `/dossiers/{domain}/evidence` |

### R2.130  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 264)
- Text:

> | `dossier-refresh` | Button. Sends `POST /dossiers/{domain}/refresh` |

### R2.131  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 265)
- Text:

> | `refresh-error` | Error message, when a refresh is refused |

### R2.132  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 266)
- Text:

> | `refresh-uncertain` | Shown when the outcome of a refresh is unknown (below) |

### R2.133  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 267)
- Text:

> | `dossier-reload` | Button. Reads the dossier again without starting a build |

### R2.134  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 268)
- Text:

> | `dossier-not-found` | Shown instead of the fields when no dossier exists for the domain |

### R2.135  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 270)
- Text:

> `data-value` is the API value as text: a string value unchanged, an integer in plain decimal digits.

### R2.136  [pkg ALL] [open]
- Section: Dossier — `/dossiers/{domain}` (spec line 273)
- Text:

> While the dossier's state is `building`, the screen reads the dossier again at least every 2 seconds until the state is `ready` or `failed`, and then shows the new fields without a manual reload.

### R2.137  [pkg R2U2] [open]
- Section: Evidence — `/dossiers/{domain}/evidence` (spec line 281)
- Text:

> | `evidence-{field}` | One container per field, six in all. Children in API `candidates` order |

### R2.138  [pkg R2U2] [open]
- Section: Evidence — `/dossiers/{domain}/evidence` (spec line 282)
- Text:

> | `candidate-{field}-{n}` | The field's `n`th candidate, counting from 1. Text contains the formatted value and the excerpt. Carries `data-value`, `data-provider`, `data-kind`, `data-url`, `data-published-at` (the RFC 3339 `published_at`, empty when null) and `data-selected="true"` or `"false"` |

### R2.139  [pkg R2U2] [open]
- Section: Evidence — `/dossiers/{domain}/evidence` (spec line 283)
- Text:

> | `evidence-empty-{field}` | Shown instead of candidates when the field has none |

### R2.140  [pkg R2U2] [open]
- Section: Contested fields — `/contested` (spec line 289)
- Text:

> | `contested-list` | Container. Children ordered by domain ascending, then by field in the order of the table in `stage-1.md` §4 |

### R2.141  [pkg R2U2] [open]
- Section: Contested fields — `/contested` (spec line 290)
- Text:

> | `contested-item-{domain}-{field}` | One per contested field of any dossier. Carries `data-value` for the selected value. Text contains the domain, the field and every distinct candidate value. Links to `/dossiers/{domain}/evidence` |

### R2.142  [pkg R2U2] [open]
- Section: Contested fields — `/contested` (spec line 291)
- Text:

> | `empty-contested` | Shown instead of the list when no field is contested |

### R2.143  [pkg R2U1] [open]
- Section: Refresh and competing clients (spec line 295)
- Text:

> After any successful action, the data on the same page must show the new state without a manual reload.

### R2.144  [pkg R2U1] [open]
- Section: Refresh and competing clients (spec line 295)
- Text:

> Navigation must wait for the write to succeed before it refreshes the data.

### R2.145  [pkg R2U1] [open]
- Section: Refresh and competing clients (spec line 295)
- Text:

> Any mechanism is fine, including a full navigation.

### R2.146  [pkg R2U1] [open]
- Section: Refresh and competing clients (spec line 295)
- Text:

> Apart from the reading while a dossier is `building`, there is no live-update requirement: another client may change state, but this browser need only read again after its own action, an explicit reload or a build it is waiting on.

### R2.147  [pkg R2U1] [open]
- Section: Refresh and competing clients (spec line 301)
- Text:

> - `dossier-reload` reads the dossier again. **Latest read wins:** a delayed earlier read must
>   not overwrite a later one, including when responses arrive out of order. This applies to the
>   reads while a dossier is `building` as well.

### R2.148  [pkg R2U1] [open]
- Section: Refresh and competing clients (spec line 304)
- Text:

> - Another client may refresh a dossier after this browser reads it. A refresh from this
>   browser while that build runs is answered 202 like any other and the screen follows the
>   running build to its end.

### R2.149  [pkg R2U1] [open]
- Section: Refresh and competing clients (spec line 307)
- Text:

> - If a research or refresh response is lost, including after the request commits, show
>   `research-uncertain` or `refresh-uncertain` (nonempty text), not `research-error` or
>   `refresh-error`. Keep the request retryable with the **same key and body**. A successful
>   retry removes both the error and the uncertainty elements, shows the dossier, and starts at
>   most one build. Unknown outcomes are not confirmed refusals.

### R2.150  [pkg R2U1] [open]
- Section: Refresh and competing clients (spec line 313)
- Text:

> No background polling beyond the reading while `building`, live synchronization, or recovery across page reloads is required.

### R2.151  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 318)
- Text:

> A stage-2 service must accept an export produced by the same team's stage-1 service.

### R2.152  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 318)
- Text:

> A browser signed in before that export/import upgrade must remain signed in afterwards.

### R2.153  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 318)
- Text:

> Imported dossiers appear in the list and on their screens.

### R2.154  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 318)
- Text:

> Each imported field gains one candidate for every value that text the providers served to the dossier's last stage-1 build that completed `ready` supports for that field (`stage-1.md` §4), once for each page whose served text supports it.

### R2.155  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 318)
- Text:

> The candidate's excerpt is taken from that text and supports the value; its `provider` is the provider that served that text, its `kind` and `published_at` are as the exported state records them or else null, and its `retrieved_at` is the dossier's `researched_at`.

### R2.156  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 318)
- Text:

> Each imported field's `value`, `status` and `citations` then follow from its candidates by the selection rule and Status, as after a build.

### R2.157  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 318)
- Text:

> A research or refresh request whose response was lost before export remains retryable after import with the same body and key; the UI must recover the original response and show the imported dossier.

### R2.158  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 318)
- Text:

> These requirements apply when import completes between browser requests; migration during an in-flight request is not required.

### R2.159  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 318)
- Text:

> No page reload or new screen is required.

### R2.160  [pkg R2S] [open]
- Section: Existing clients after an upgrade (spec line 333)
- Text:

> The candidates of an imported dossier are replaced by those of its next completed build.


## Status table (stage 2)

Per package, final. FROZEN REVISION: main 03740bec096bc1e68ffc32ed389dae0f9094ec53 (FINAL ACCEPT by @gatekeeper). Acceptance suite 221 passed, 0 failed; unit 289 passed; service OK; Node UI tests 7 pass; isolated event check exit 0 (stage-1 122/122, stage-2 shipped 12/12, 0 leaks, 0 fabrications, 0 errors).

| Pkg | Ledger scope | Status | Evidence |
|---|---|---|---|
| R2R | all `[pkg R2R]` | accepted | merged 2296a62; R2R-TRACE.md ec04458; R2.18-R2.41 optional, not implemented (Rul-S2-4), mandatory-clause check pending at final review; R2.13, R2.14, R2.15, R2.24, R2.45 not observable black-box (Prover report) |
| R2S | all `[pkg R2S]` | accepted | merged f0e601e (R2S-b 1a0f8f3, R2S-c caf2ec1); selection tests PT2-a/b/d |
| R2U1 | all `[pkg R2U1]` | accepted | merged 3261d4e; UI-TRACE.md 011083a; h1 hotfix merged; browser tests test_ui_browser, test_ui_faults, test_ui_polling, test_ui_latest |
| R2U2 | all `[pkg R2U2]` | accepted | merged 0b129c7; test_ui_evidence |
| ALL | process/global (R2.1-R2.3 etc.) | accepted | FINAL ACCEPT, isolated check on 03740be |

Open risks: the provider tie-break is an equivalent mutant (dropped by ruling); the 80-unit budget cap is not testable black-box (all corpora spend 54 or fewer units); /contested reads N+1.

## In-flight list (stage 2)

(empty: stage 2 frozen at 03740bec096bc1e68ffc32ed389dae0f9094ec53)

## Rejections (stage 2)
No package was rejected. FINAL ACCEPT was held once: defect planting found 3 defects no test caught (stale overwrite in latest.js, reversed URL tie-break, dedupe on value+url+excerpt) plus a reversed value tie-break. The Prover added tests for all four; the provider tie-break is an equivalent mutant (Rul: dropped).

## Frozen (stage 2)
Stage 2 frozen at main 03740bec096bc1e68ffc32ed389dae0f9094ec53. Copied here as the stage-3 seed; everything above this line is the frozen stage-2 ledger.

# STAGE 3 (spec stage-3.md; started 2026-11-21T07:33Z)

## Packages (stage 3)

| Pkg | Owner | Scope | Order |
|---|---|---|---|
| R3S | @gatekeeper | Seed: stage-3/ is a plain copy of frozen stage 2 (03740be); builds and starts | 1st (merge now) |
| R3A | @builder-a | Build records (per build: time, outcome, spend, selected fields, candidates, page versions), `true_from`/`learned_at` on candidates and fields, history entries (`initial`/`change`/`correction`), change feed and `GET /changes`, `GET /dossiers/{domain}/history`, `GET /dossiers/{domain}?as_of=`, concurrency (one build, entries once) | 1st after the seed |
| R3D | @builder-a | Restarts: durable state on the container filesystem (accounts, tokens, dossiers, builds, history, feed with `seq`, idempotency records, clock), atomic writes, recovery at start | after R3A |
| R3B | @builder-b | `executives` field (Appendix A titles cfo/coo/cto in `support.py`, candidates with `title`, selection per title, status, citations, history typing), `Effective:` header parsing and candidate `true_from`, `GET /dossiers/{domain}/values?true_at=` (page versions) as a pure function over build records | in parallel with R3A (agree the build-record shape with builder-a first) |
| R3C | @builder-b | Upgrades: stage-1 and stage-2 export import (builds, versions, history `initial`, `learned_at`, `executives` unknown), stage-3 export/import round trip of history, feed and builds | after R3B and R3A |
| R3U | @builder-a (after R3D) or @builder-b | UI: the screens of stage 2 must keep working with the seventh field; `executives` takes no data-testid of stage 2; `/contested` counts only the six fields | last, small |
| PT3 | @prover | Independent black-box acceptance tests from the spec, including restart tests, as_of/values/history/changes, executives, upgrades, concurrency, defect-planting readiness | in parallel from the start |
| GK | @gatekeeper | Review, check runs, merging, final isolated check, defect planting | as packages land |

## Rulings (stage 3)

- **Rul-S3-1 (build record).** The service keeps one record per build in build order: `{index, time (the §8 Builds time of the build), state ready|failed, spent_units, fields (selected value, true_from, learned_at, citations, candidates for all seven fields), versions (one per gathered URL: url, true_from, candidates)}`. History, feed, as_of and values are all derived from or stored beside these records. R3A owns the record shape; R3B consumes it. Imports (R3C) create records.
- **Rul-S3-2 (durability).** Every state change that a response acknowledges must be on disk before that response is sent: write the whole state (or a transaction) with fsync and an atomic rename, or SQLite with synchronous=FULL. A data directory on the container filesystem (not a tmpfs), path from an env var with a default inside the image. A build that was running at an abrupt stop is not required to survive; on start a dossier left `building` becomes `failed` without adding history or feed entries.
- **Rul-S3-3 (time and ties).** All `learned_at`, `as_of` comparisons use parsed instants (offsets normalised); ties between ready builds with the same instant go to the later build in build order. `as_of` selects only ready builds.
- **Rul-S3-4 (feed seq).** `seq` is assigned inside the same atomic step that appends the entries of one build, so concurrent refreshes cannot repeat or skip a `seq`, and it continues from the largest persisted `seq` after a restart.
- **Rul-S3-5 (executives is outside the six-field screens).** The stage-2 UI keeps its testids for the six fields only; an `executives` section may use other markup. `/contested` ignores `executives`.
- **Rul-S3-6 (ledger statements).** Entries below are mechanical verbatim blocks of stage-3.md (paragraph, bullet, table row or code block), numbered R3.n in spec order; table header rows are context, not requirements.

## Requirements (spec stage-3.md; every quote is verbatim; status: open | built | tested | accepted)
### R3.1  [pkg ALL] [open]
- Section: Dossier — Stage 3: change over time (spec line 3)
- Text:

> The requirements from stages 1 and 2 continue to apply, with the additions below.
> Numbered section references such as §4 and §8 refer to `stage-1.md`.

### R3.2  [pkg ALL] [open]
- Section: Dossier — Stage 3: change over time (spec line 6)
- Text:

> Companies change, and the web changes with them: a refresh may be served pages that earlier
> builds were not, and may no longer be served pages they were. Sources also correct
> themselves. A dossier now keeps the history of each field, answers as it stood at an earlier
> time, and publishes its changes in a feed. It also names the company's executives.

### R3.3  [pkg ALL] [open]
- Section: Dossier — Stage 3: change over time (spec line 11)
- Text:

> The following applies to all operations, in addition to the earlier lists:

### R3.4  [pkg ALL] [open]
- Section: Dossier — Stage 3: change over time (spec line 13)
- Text:

> 4. Every change to a selected value appears exactly once in the change feed, at the time this
>    stage assigns to it.

### R3.5  [pkg R3A] [open]
- Section: Two times per value (spec line 18)
- Text:

> Every candidate and every selected value now has two times:

### R3.6  [pkg R3A] [open]
- Section: Two times per value (spec line 20)
- Text:

> - **`true_from`**: the date from which the evidence says the value holds. A page states it
>   in the header line `Effective: <YYYY-MM-DD>`. A page with no valid `Effective` line takes
>   the date part, in UTC, of its `published_at`; with neither, `true_from` is null.

### R3.7  [pkg R3A] [open]
- Section: Two times per value (spec line 23)
- Text:

> - **`learned_at`**: when this service first had the value. For a candidate, it is the time
>   (§8, Builds) of the first build that gathered a candidate with the same field, value, URL
>   and provider. For a selected value, it is the time of the build that made it the
>   selected value.

### R3.8  [pkg R3A] [open]
- Section: Two times per value (spec line 28)
- Text:

> Candidates gain `true_from` and `learned_at`. `retrieved_at` (stage 2) stays the time of the
> build that gathered the candidate in the current candidate set. A selected value's
> `true_from` is that of its selected candidate.

### R3.9  [pkg R3A] [open]
- Section: Two times per value (spec line 32)
- Text:

> Each field of `GET /dossiers/{domain}` also carries the selected value's `true_from` and
> `learned_at`. Both are null when the field is `unknown`. In an `as_of` response these
> describe the selected value at that snapshot, using no later history.

### R3.10  [pkg R3A] [open]
- Section: Two times per value (spec line 36)
- Text:

> The selection rule in `stage-2.md` is unchanged.

### R3.11  [pkg R3B] [open]
- Section: Executives (spec line 40)
- Text:

> A dossier has a seventh field, `executives`. The `fields` of every response that lists a
> dossier's fields hold it, after the six fields of §4. A research run (§4) still asks for the
> six fields of §4 only.

### R3.12  [pkg R3B] [open]
- Section: Executives (spec line 44)
- Text:

> Its value is an array with one object `{ "title": T, "name": N }` for each title below that
> has a selected person, in the order `cfo`, `coo`, `cto`. These objects are the field's
> **members**. When no title has a selected person, the value is null and the field is
> `unknown`.

### R3.13  [pkg R3B] [open]
- Section: Executives (spec line 49)
- Text:

> For Appendix A, each title is a field with these statement phrases and with the format and
> normalisation of `ceo` (A.4, A.5), the title's own statement phrases taking the place of
> those for `ceo`:

### R3.14  [pkg R3B] [open]
- Section: Executives (spec line 53)
- Text:

> | Title | Statement phrases |

### R3.15  [pkg R3B] [open]
- Section: Executives (spec line 55)
- Text:

> | `cfo` | `chief financial officer`, `CFO` |

### R3.16  [pkg R3B] [open]
- Section: Executives (spec line 56)
- Text:

> | `coo` | `chief operating officer`, `COO` |

### R3.17  [pkg R3B] [open]
- Section: Executives (spec line 57)
- Text:

> | `cto` | `chief technology officer`, `CTO` |

### R3.18  [pkg R3B] [open]
- Section: Executives (spec line 59)
- Text:

> A candidate of `executives` is a candidate of one title: it carries `title` beside `value`,
> and its `value` is the person's name. A research claim is never a candidate of
> `executives`.

### R3.19  [pkg R3B] [open]
- Section: Executives (spec line 63)
- Text:

> ```json
> { "value": [ { "title": "cfo", "name": "Ana Silva" }, { "title": "cto", "name": "Ben Okafor" } ],
>   "status": "known", "true_from": "2025-09-01", "learned_at": "2026-03-01T09:00:00+00:00",
>   "citations": [ { "url": "https://acme-robotics.test/team",
>                    "excerpt": "Ana Silva is the chief financial officer of Acme Robotics.",
>                    "provider": "nimble" },
>                  { "url": "https://bizdata.test/acme-robotics",
>                    "excerpt": "Acme Robotics CTO: Ben Okafor.", "provider": "tavily" } ],
>   "candidates": [ { "title": "cfo", "value": "Ana Silva", "...": "...", "selected": true },
>                   { "title": "cto", "value": "Ben Okafor", "...": "...", "selected": true } ] }
> ```

### R3.20  [pkg R3B] [open]
- Section: Executives (spec line 75)
- Text:

> The selection rule in `stage-2.md` runs separately over the candidates of each title.

### R3.21  [pkg R3B] [open]
- Section: Executives (spec line 77)
- Text:

> - `selected` is true on the highest-ranked candidate of each title that has candidates, and
>   false on the others.

### R3.22  [pkg R3B] [open]
- Section: Executives (spec line 79)
- Text:

> - `candidates` lists every candidate by title, in the order above, then in rank order.

### R3.23  [pkg R3B] [open]
- Section: Executives (spec line 80)
- Text:

> - `citations` are, for each member in order, the `url`, `excerpt` and `provider` of every
>   candidate with the member's title and name, in rank order.

### R3.24  [pkg R3B] [open]
- Section: Executives (spec line 82)
- Text:

> - `status` is `unknown` when the value is null, `contested` when the candidates of some
>   title carry two or more different names, and `known` otherwise.

### R3.25  [pkg R3B] [open]
- Section: Executives (spec line 84)
- Text:

> - A candidate's `learned_at` is the time of the first build that gathered a candidate with
>   the same title, name, URL and provider.

### R3.26  [pkg R3B] [open]
- Section: Executives (spec line 86)
- Text:

> - A member's `true_from` is that of its title's selected candidate. The field's `true_from`
>   is the latest of its members' `true_from`, or null when any member's is null.

### R3.27  [pkg R3B] [open]
- Section: Executives (spec line 88)
- Text:

> - `GET /dossiers/{domain}/values` chooses each title's person from the candidates at
>   `true_at` and gives the value, `true_from` and `citations` from them by these rules.

### R3.28  [pkg R3B] [open]
- Section: Executives (spec line 91)
- Text:

> A history and feed entry for `executives` is typed by title, in place of the table in
> Changes and corrections. A title **differs** between the earlier and the new value when
> exactly one of them has a member with that title, or both have one and their names differ. A
> differing title counts as a correction when both values have a member with that title, both
> members' `true_from` are not null, and the new member's is on or before the earlier
> member's. The entry is `correction` when every differing title counts as a correction, and
> `change` otherwise.

### R3.29  [pkg R3B] [open]
- Section: Executives (spec line 99)
- Text:

> The `data-testid` attributes of the screens in `stage-2.md` name only the six fields of §4:
> `executives` takes none of them, and a screen that shows it does so with other markup. On
> `/contested`, "no field is contested" means none of those six fields is.

### R3.30  [pkg R3A] [open]
- Section: Changes and corrections (spec line 105)
- Text:

> When a build completes `ready`, each field whose selected value differs from its selected
> value before the build gets one history entry, and one feed entry, of one of two types:

### R3.31  [pkg R3A] [open]
- Section: Changes and corrections (spec line 108)
- Text:

> | Type | When |

### R3.32  [pkg R3A] [open]
- Section: Changes and corrections (spec line 110)
- Text:

> | `correction` | Both the earlier and the new value are not null, and the new value's `true_from` is on or before the earlier value's `true_from` |

### R3.33  [pkg R3A] [open]
- Section: Changes and corrections (spec line 111)
- Text:

> | `change` | Every other difference, including a value appearing where there was none, a value disappearing, and either `true_from` being null |

### R3.34  [pkg R3A] [open]
- Section: Changes and corrections (spec line 113)
- Text:

> A field's first selected value, set by the dossier's first build that completes `ready`,
> gets a history entry of type `initial` and no feed entry. A field that is `unknown` after
> that build gets its first entry when it first gets a value, and that entry is a `change`.

### R3.35  [pkg R3A] [open]
- Section: Changes and corrections (spec line 117)
- Text:

> A build that completes with the same selected value for a field adds nothing for it, even
> when its candidates, citations or `true_from` differ. A `failed` build adds nothing. Concurrent refreshes
> of one dossier run one build (§8) and so add each entry once.

### R3.36  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}?as_of=` (spec line 123)
- Text:

> ```http
> GET /dossiers/acme-robotics.test?as_of=2026-03-15T00:00:00+00:00
> ```

### R3.37  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}?as_of=` (spec line 127)
- Text:

> Returns the dossier as this service had it at `as_of`: the fields, candidates and
> `researched_at` of the latest build that completed `ready` and whose time is at or before
> `as_of`, decided by `learned_at`, never by `true_from`. `state` is `ready`. `spent_units` is
> the total of the builds whose time is at or before `as_of`.

### R3.38  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}?as_of=` (spec line 132)
- Text:

> When several ready builds have the same time, return the last of them in build order.
> This also applies when equivalent RFC 3339 timestamps use different offsets. The clock
> need not advance between builds.

### R3.39  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}?as_of=` (spec line 136)
- Text:

> | Case | Response |

### R3.40  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}?as_of=` (spec line 138)
- Text:

> | `as_of` is not an RFC 3339 timestamp with an explicit offset | 422 `validation_failed` |

### R3.41  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}?as_of=` (spec line 139)
- Text:

> | No build of the dossier completed `ready` with a time at or before `as_of` | 404 `not_found` |

### R3.42  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}?as_of=` (spec line 140)
- Text:

> | No dossier for the domain | 404 `not_found` |

### R3.43  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}?as_of=` (spec line 142)
- Text:

> Without `as_of`, `GET /dossiers/{domain}` is unchanged.

### R3.44  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 146)
- Text:

> ```http
> GET /dossiers/acme-robotics.test/values?true_at=2025-06-01&as_of=2026-04-01T09:00:00+00:00
> ```

### R3.45  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 150)
- Text:

> Returns, for each field, the value that the evidence this service had at `as_of` says held
> on the date `true_at`. `as_of` defaults to the current time (§8).

### R3.46  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 153)
- Text:

> A **page version** is what one ready build gathered from one URL: its candidates and its
> `true_from`. The versions of a URL known at `as_of` are those gathered by ready builds whose
> time is at or before `as_of`, taken in build order. Each version holds from its `true_from`.
> When a later version of the same URL is gathered, it replaces every earlier version of that
> URL whose `true_from` is on or after its own. The latest earlier version that it does not
> replace stops holding on the later version's `true_from`. A version whose `true_from` is
> null holds from no date, and a later version with a null `true_from` replaces every earlier
> version of its URL. A gathered version with no candidates still replaces or ends earlier
> versions by this rule.

### R3.47  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 163)
- Text:

> The candidates **at `true_at`** are those of every version that holds on that date. Each
> field's value is chosen from them by the selection rule in `stage-2.md`, and its
> `true_from` is that of the chosen candidate.

### R3.48  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 167)
- Text:

> ```json
> { "domain": "acme-robotics.test", "true_at": "2025-06-01",
>   "as_of": "2026-04-01T09:00:00+00:00",
>   "fields": { "ceo": { "value": "Dana Ruiz", "true_from": "2021-04-01",
>                        "citations": [ { "url": "...", "excerpt": "...", "provider": "nimble" } ] },
>               "...": "..." } }
> ```

### R3.49  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 175)
- Text:

> A field with no candidate at `true_at` has `"value": null`, `"true_from": null`,
> `"citations": []`. Citations are those of the candidates at `true_at` with the chosen value.

### R3.50  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 178)
- Text:

> | Case | Response |

### R3.51  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 180)
- Text:

> | `true_at` missing or not a `YYYY-MM-DD` date, or `as_of` not an RFC 3339 timestamp with an explicit offset | 422 `validation_failed` |

### R3.52  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 181)
- Text:

> | No dossier for the domain, or no build of it completed `ready` with a time at or before `as_of` | 404 `not_found` |

### R3.53  [pkg R3B] [open]
- Section: `GET /dossiers/{domain}/values?true_at=` (spec line 183)
- Text:

> For state imported from an export, the builds and versions are those Upgrades gives.

### R3.54  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}/history` (spec line 187)
- Text:

> ```json
> {
>   "domain": "acme-robotics.test",
>   "fields": {
>     "ceo": [
>       { "type": "initial", "value": "Dana Ruiz", "true_from": "2021-04-01",
>         "learned_at": "2026-03-01T09:00:00+00:00",
>         "citations": [ { "url": "...", "excerpt": "...", "provider": "nimble" } ] },
>       { "type": "change", "value": "Lee Park", "true_from": "2026-03-20",
>         "learned_at": "2026-04-01T09:00:00+00:00",
>         "citations": [ { "url": "...", "excerpt": "...", "provider": "tavily" } ] }
>     ],
>     "legal_name": [ { "...": "..." } ],
>     "hq_city": [],
>     "founded_year": [ { "...": "..." } ],
>     "headcount_range": [ { "...": "..." } ],
>     "funding_total": [ { "...": "..." } ],
>     "executives": [ { "...": "..." } ]
>   }
> }
> ```

### R3.55  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}/history` (spec line 209)
- Text:

> - `fields` holds all seven fields. Each list is in the order the entries were added, oldest
>   first.

### R3.56  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}/history` (spec line 211)
- Text:

> - An entry's `value`, `true_from`, `learned_at` and `citations` are those of the selected
>   value it records. An entry whose value is null has `"true_from": null` and
>   `"citations": []`.

### R3.57  [pkg R3A] [open]
- Section: `GET /dossiers/{domain}/history` (spec line 214)
- Text:

> - No dossier for the domain is 404 `not_found`.

### R3.58  [pkg R3A] [open]
- Section: `GET /changes` (spec line 218)
- Text:

> ```http
> GET /changes?since=0&limit=50
> ```

### R3.59  [pkg R3A] [open]
- Section: `GET /changes` (spec line 222)
- Text:

> ```json
> {
>   "changes": [
>     { "seq": 1, "domain": "acme-robotics.test", "field": "ceo", "type": "change",
>       "from": "Dana Ruiz", "to": "Lee Park", "true_from": "2026-03-20",
>       "learned_at": "2026-04-01T09:00:00+00:00" }
>   ],
>   "has_more": false
> }
> ```

### R3.60  [pkg R3A] [open]
- Section: `GET /changes` (spec line 233)
- Text:

> The feed holds every `change` and `correction` entry of every dossier.

### R3.61  [pkg R3A] [open]
- Section: `GET /changes` (spec line 235)
- Text:

> - `seq` is a positive integer, unique across the feed, and larger for every later entry.
>   Entries added by one build are numbered in the order of the fields in `stage-1.md` §4,
>   then `executives`.

### R3.62  [pkg R3A] [open]
- Section: `GET /changes` (spec line 238)
- Text:

> - `from` and `to` are the earlier and the new selected value, either of which may be null.
>   `true_from` is the new value's. `learned_at` is the time of the build that added the
>   entry.

### R3.63  [pkg R3A] [open]
- Section: `GET /changes` (spec line 241)
- Text:

> - `since` defaults to 0 and lists only entries whose `seq` is greater than it. It is an
>   integer, 0 or more. Entries are ordered by `seq` ascending.

### R3.64  [pkg R3A] [open]
- Section: `GET /changes` (spec line 243)
- Text:

> - `limit` defaults to 50, range 1 to 200. `has_more` is true when entries exist beyond the
>   last one returned.

### R3.65  [pkg R3C] [open]
- Section: Upgrades (spec line 248)
- Text:

> A stage-3 service must accept an export produced by the same team's stage-1 or stage-2
> service. Every imported field that has a value gets one history entry of type `initial`,
> with `learned_at` the dossier's `researched_at` and `true_from` null unless the exported
> state records the dates that give it. The feed starts empty; the first build after import
> compares its selected values with the imported ones. Existing tokens, dossiers and completed
> idempotent responses survive the import as in `stage-1.md` §10, and the history and feed
> of a stage-3 export survive a stage-3 import unchanged. So do its builds: after a
> stage-3 import, `?as_of=` and `/values` answer as they did in the exporting service.

### R3.66  [pkg R3C] [open]
- Section: Upgrades (spec line 257)
- Text:

> State imported from a stage-1 export counts as one build that completed `ready` at the
> dossier's `researched_at`, and each imported candidate's URL as one version gathered by it;
> imported candidates have `learned_at` equal to their `retrieved_at`. An `as_of` at or after
> that time and before the next build returns the imported fields, and an earlier `as_of` is
> 404 `not_found`. An imported dossier whose `researched_at` is null answers every `as_of` with
> 404 `not_found` until a build completes.

### R3.67  [pkg R3C] [open]
- Section: Upgrades (spec line 264)
- Text:

> State imported from a stage-2 export keeps the builds that the stage-2 service made, each
> with its time, its outcome and its spending. Each of them that completed `ready` keeps the
> candidates it gathered and, for each URL it gathered, one page version whose `true_from`
> follows from that page's `Effective` and `Published` lines as that build gathered them
> (Two times per value). State that the stage-2 service had itself imported counts as one
> build that completed `ready` at the dossier's `researched_at`. `?as_of=`, `/values` and each
> candidate's `learned_at` then answer as if this service had made those builds. History is
> still one `initial` entry per field that has a value, as above, and an `as_of` response takes
> each field's `learned_at` and `true_from` from that history (Two times per value).

### R3.68  [pkg R3C] [open]
- Section: Upgrades (spec line 274)
- Text:

> An export of a stage-1 or stage-2 service has no `executives` candidates. After its import,
> `executives` is `unknown`, in the imported state and in every build kept from the export,
> and has no history entry; the first build that completes `ready` with a value for it adds a
> `change`, or an `initial` entry when it is the dossier's first build that completes `ready`.

### R3.69  [pkg R3A] [open]
- Section: Concurrency (spec line 281)
- Text:

> Concurrent refreshes and reads must produce the same results as executing them one at a time
> in some order. No change appears twice in the feed, and none is missing from it.

### R3.70  [pkg R3D] [open]
- Section: Restarts (spec line 286)
- Text:

> This row replaces the Disk row of the resource limits in `stage-1.md` §2:

### R3.71  [pkg R3D] [open]
- Section: Restarts (spec line 288)
- Text:

> | Limit | Value |

### R3.72  [pkg R3D] [open]
- Section: Restarts (spec line 290)
- Text:

> | Disk | the container's filesystem; it survives a container restart |

### R3.73  [pkg R3D] [open]
- Section: Restarts (spec line 292)
- Text:

> The container may be stopped abruptly at any time, with no warning and no time to finish what
> the service is doing, and then started again. The sentence "State need not survive an
> abrupt container restart" in `stage-1.md` §10 no longer applies. When no build is running
> at the stop, the service answers after the restart exactly
> as it did before the stop:

### R3.74  [pkg R3D] [open]
- Section: Restarts (spec line 298)
- Text:

> - Every account signs in with its password, and every bearer token is valid.

### R3.75  [pkg R3D] [open]
- Section: Restarts (spec line 299)
- Text:

> - Every dossier answers `GET /dossiers/{domain}`, with and without `as_of`,
>   `GET /dossiers/{domain}/values` and `GET /dossiers/{domain}/history` as before, and
>   `GET /dossiers` lists the same dossiers.

### R3.76  [pkg R3D] [open]
- Section: Restarts (spec line 302)
- Text:

> - The change feed holds the same entries with the same `seq`. An entry added after the
>   restart has a larger `seq` than every entry before it.

### R3.77  [pkg R3D] [open]
- Section: Restarts (spec line 304)
- Text:

> - A replay of a completed idempotent request answers as §7 requires.

### R3.78  [pkg R3D] [open]
- Section: Restarts (spec line 305)
- Text:

> - The clock reads the time it read before the stop until reset or `POST /_test/clock` moves
>   it.


## Status table (stage 3)

| Pkg | Ledger scope | Status |
|---|---|---|
| R3S | seed | open |
| R3A | all `[pkg R3A]` | open |
| R3D | all `[pkg R3D]` | open |
| R3B | all `[pkg R3B]` | open |
| R3C | all `[pkg R3C]` | open |
| R3U | UI part of R3.* | open |
| ALL | process/global | open |

## In-flight list (stage 3)

| Item | Holder | Latest report |
|---|---|---|
| stage-3 seed merge | @gatekeeper | requested |
| R3A | @builder-a | assigned |
| R3B | @builder-b | assigned |
| PT3 | @prover | assigned |

## Rejections (stage 3)
(none yet)
