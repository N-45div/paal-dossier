# UI trace — stage 2 ledger ids R2.76–R2.150 (builder-a)

Each line gives the ledger id, where the behaviour lives, and how it was checked. Verification keys:

- **B** — headless Chromium (Playwright) run by builder-a against a stub-build instance (research with a stubbed build; one contested field). Runs were at 375 px and 1280 px. The scripts live in builder-a's scratch area, not in the repo.
- **S** — service test in `tests/service/test_ui.py` or a server-side HTML check (`curl`, in-process client).
- **C** — read in code only. Not exercised.
- **U** — Node unit test (`node --test tests/ui/latest.test.mjs tests/ui/pending.test.mjs`, Node 22).
- **X** — not verified.

Where a line lists several keys, each key covers only the part it names.

| Id | Requirement (short) | Code | Checked |
|---|---|---|---|
| R2.76 | Listed screens reachable by URL | `app/ui/routes.py` | S: `/`, `/signup`, `/login`, `/dossiers/{domain}`, `/dossiers/{domain}/evidence`, `/contested` return 200 HTML; B: each reached by URL |
| R2.77 | Other screens reachable through the UI | `app/ui/layout.py` (nav), `app/ui/pages.py` (dossier → evidence link) | B: nav Contested link and Evidence button followed |
| R2.78 | SSR and CSR both permitted | `app/ui/pages.py` (shells), `app/ui/static/js/*.js` (data) | C: shells are SSR, data is CSR |
| R2.79 | `/` list with search and research form | `app/ui/pages.py::HOME_BODY`, `static/js/home.js` | B: list, search, empty state, research form |
| R2.80 | `/dossiers/{domain}` state, six fields, status, citations, refresh, reload | `app/ui/pages.py::dossier_body`, `static/js/dossier.js` | B: all fields rendered, refresh and reload exercised |
| R2.81 | `/dossiers/{domain}/evidence` shows every candidate | `app/ui/evidence.py`, `static/js/evidence.js` | B: candidate lists in order at 375 and 1280 px |
| R2.82 | `/contested` shows every contested field | `app/ui/contested.py`, `static/js/contested.js` | B: one contested item listed, empty state hidden |
| R2.83 | `/signup` | `app/ui/pages.py::SIGNUP_BODY`, `static/js/auth.js` | B: signup happy path |
| R2.84 | `/login` | `app/ui/pages.py::LOGIN_BODY`, `static/js/auth.js` | X: login form not exercised in a browser |
| R2.85 | Browser and API share `/dossiers/{domain}` | `app/dossiers.py::get_one`, `app/negotiation.py`, `app/ui/routes.py` | S: shared route serves HTML and JSON |
| R2.86 | `Accept: text/html` gets UI; other requests get JSON | `app/negotiation.py::wants_html`, `app/ui/pages.py::dossier` | S: HTML with `Accept: text/html`, JSON 401 without it |
| R2.87 | `/`, evidence and contested are browser routes reading API data | `app/ui/pages.py::home`, `app/ui/evidence.py`, `app/ui/contested.py`; JS reads `/dossiers` | B: data loaded through the JSON API |
| R2.88 | Browser route domains normalised | `app/ui/pages.py::dossier`, `app/ui/pages.py::domain_screen` | S: `ACME-robotics.test.` → 302 to `acme-robotics.test`; invalid → 404 page |
| R2.89 | Expose listed `data-testid`s | `app/ui/pages.py`, `static/js/*.js` | B: every id in R2.104–R2.142 seen at least once; see the per-id lines |
| R2.90 | Extra elements permitted | `app/ui/*` | C |
| R2.91 | Coherent, presentation-ready product | `app/ui/static/app.css`, `app/ui/layout.py` | B: screenshots at 375 px reviewed; 1280 px not reviewed visually |
| R2.92 | Evidence-first character: known/unknown/contested visible | `static/js/dossier.js::renderField`, `app.css` (`.field[data-status]`) | B: status badges visible on dossier and evidence screens |
| R2.93 | Field value and status clearest, citations beside it | `static/js/dossier.js::renderField` | B: 375 px screenshot |
| R2.94 | Status, provider, kind, publication time readable | `static/js/format.js`, `static/js/evidence.js::renderCandidate` | B: provider, kind and published date shown on evidence |
| R2.95 | Consistent visual system | `app/ui/static/app.css` | C |
| R2.96 | Primary actions easy to identify | `app.css` (`.btn.primary`), `pages.py` | C: visually in screenshot only |
| R2.97 | Distinct visual states | `app.css` (`.state-*`, `.badge.*`), `format.js` labels | B: building, ready, known, unknown, contested badges seen; refused and failed states not seen |
| R2.98 | People-first formatting | `static/js/format.js` | B: `$12,000,000`, date and `Ready` labels seen |
| R2.99 | Excerpt quoted, linked to URL | `static/js/dossier.js::renderCitation`, `static/js/evidence.js` | B: blockquote and link seen |
| R2.100 | Usable at 375 px, no horizontal scroll | `app.css` (`@media (max-width: 480px)`) | B: `scrollWidth == clientWidth` at 375 px on home, dossier, evidence, contested |
| R2.101 | Visible labels, focus, contrast | `pages.py` (labels), `app.css` (`:focus-visible`, colours) | C: labels present in markup; contrast and focus not measured |
| R2.102 | Empty, loading and error states; consistent nav | `pages.py` status lines, `home.js`, `dossier.js`, `contested.js`; `layout.py` | B: empty and loading text seen; error states partly (research error, refresh uncertain) |
| R2.103 | No custom illustration needed | n/a | n/a |
| R2.104 | Signup inputs testids | `pages.py::SIGNUP_BODY` | B: `signup-email`, `signup-password`, `signup-display-name` filled |
| R2.105 | `signup-submit` | `pages.py::SIGNUP_BODY` | B: clicked |
| R2.106 | Login inputs and button testids | `pages.py::LOGIN_BODY` | X: not exercised |
| R2.107 | `auth-error` present only when there is an error | `pages.py::_auth_form`, `static/js/auth.js::showError` | X: error path not exercised in a browser |
| R2.108 | `current-user` on every screen when signed in | `layout.py`, `static/js/layout.js::renderSession` | B: shows display name on home, dossier and evidence |
| R2.109 | `logout-button` | `layout.py`, `static/js/layout.js` | B: clicked, session cleared (body `data-session="out"`) |
| R2.110 | `research-domain` input | `pages.py::HOME_BODY` | B: filled |
| R2.111 | `research-submit` sends `POST /dossiers` | `static/js/home.js` | B: request observed by route interception |
| R2.112 | `research-error` on refusal, including invalid domain | `static/js/home.js::showResearchError` | B: invalid domain shows server message |
| R2.113 | `research-uncertain` on lost response | `static/js/home.js` (`NetworkError` branch) | B: route aborted, `research-uncertain` shown, `research-error` hidden |
| R2.114 | `dossier-search` filters list as `q` | `static/js/home.js` (`loadList`) | B: typed filter; empty and match states |
| R2.115 | `dossier-list` ordered by domain | `static/js/home.js::loadList` (order from API) | C: relies on API order |
| R2.116 | `dossier-item-{domain}` with `data-state`, text and link | `static/js/home.js::renderItem` | B: text contains domain and legal name; `data-state` observed |
| R2.117 | `empty-dossiers` | `pages.py::HOME_BODY`, `home.js` | B: shown on empty list and no-match search |
| R2.118 | 202 or 200 opens normalised dossier page | `static/js/home.js` (research submit) | B: navigation to `/dossiers/acme-robotics.test` |
| R2.119 | Existing dossier opens with no new build | `static/js/home.js`, `app/dossiers.py::create` (200) | B: research of existing domain opened the page; no build confirmed by state check |
| R2.120 | `dossier-domain` text is exact normalised domain | `pages.py::dossier_body` | B: text equals domain |
| R2.121 | `dossier-state` text exactly `building`, `ready`, `failed` | `static/js/dossier.js::renderSummary` | B: `building` then `ready` observed |
| R2.122 | `dossier-spent` formatted with `data-units` | `static/js/dossier.js::renderSummary` | B: `34 units spent`, `data-units="34"` |
| R2.123 | `dossier-researched-at` absent when null | `static/js/dossier.js::renderSummary` | B: visible when set; absent-when-null not seen |
| R2.124 | `field-{field}` six in order, `data-status` | `static/js/dossier.js::renderField`, `app/dossiers.py` (order) | B: six fields, `data-status="known"` and `unknown` |
| R2.125 | `field-value-{field}` formatted, `data-value`, only when not null | `static/js/dossier.js::renderField` | B: `$12,000,000` with `data-value="12000000"`; absence for CEO seen |
| R2.126 | `field-contested-{field}` only when contested | `static/js/dossier.js::renderField` | B: not seen on dossier screen; the evidence/contested screens were checked instead |
| R2.127 | `field-citations-{field}` container in API order | `static/js/dossier.js::renderField` | B: container present per field |
| R2.128 | `citation-{field}-{n}` with excerpt, link href, `data-provider` | `static/js/dossier.js::renderCitation` | B: `data-provider="nimble"` and `href` checked |
| R2.129 | `dossier-evidence-link` | `pages.py::dossier_body` | B: clicked, opened evidence |
| R2.130 | `dossier-refresh` sends `POST /dossiers/{domain}/refresh` | `static/js/dossier.js` (refresh click) | B: refresh observed, building then ready |
| R2.131 | `refresh-error` when refused | `static/js/dossier.js::showRefreshError` | C: refused refresh not exercised |
| R2.132 | `refresh-uncertain` on lost response | `static/js/dossier.js` (`NetworkError` branch) | B: route aborted, `refresh-uncertain` shown, retry started build |
| R2.133 | `dossier-reload` reads without build | `static/js/dossier.js` (reload click → `read`) | B: reload read, state `ready` |
| R2.134 | `dossier-not-found` | `pages.py::dossier_not_found_body`, `static/js/dossier.js::showNotFound` | B: `/dossiers/nobody.test` shows it |
| R2.135 | `data-value` plain text, string unchanged, integer digits | `static/js/dossier.js`, `format.js` | B: `12000000`, `2014` |
| R2.136 | Poll at least every 2 s while building, then show fields | `static/js/dossier.js::schedulePoll` (1500 ms) | B: building observed then ready without reload; interval not timed |
| R2.137 | `evidence-{field}` six containers, API order | `static/js/evidence.js::renderField` | B: `evidence-hq_city` has two candidates in API order |
| R2.138 | `candidate-{field}-{n}` with data attributes and `data-selected` | `static/js/evidence.js::renderCandidate` | B: `data-selected` true and false seen; `data-published-at` seen on candidate 2 |
| R2.139 | `evidence-empty-{field}` | `static/js/evidence.js::renderField` | B: `evidence-empty-ceo` visible |
| R2.140 | `contested-list` ordered by domain, then field | `static/js/contested.js::read` (sort by domain; field order from `Object.entries`) | B: one item; order across several domains C |
| R2.141 | `contested-item-{domain}-{field}` with `data-value`, text, link | `static/js/contested.js::renderItem` | B: `data-value="Lisbon"`, text lists both values, link opens evidence |
| R2.142 | `empty-contested` | `pages.py`/`contested.py::CONTESTED_BODY`, `contested.js` | B: hidden when contested item present; visible-when-empty not seen |
| R2.143 | Same page shows new state after a successful action | `static/js/dossier.js` (refresh success → `read()`), `home.js` (navigate) | B: refresh → building → ready without reload |
| R2.144 | Navigation waits for write | `static/js/home.js` (navigate after 202/200 only) | B: navigation only after success; uncertain case stayed on page |
| R2.145 | Any mechanism | n/a | n/a |
| R2.146 | No live-update beyond building/own action | `static/js/dossier.js` (polls only while building) | C |
| R2.147 | Latest read wins, including out-of-order and while building | `static/js/latest.js::createLatestReads`, used in `dossier.js`, `home.js`, `evidence.js`, `contested.js` | U: `node --test tests/ui/latest.test.mjs` (3 tests pass); not exercised in a browser |
| R2.148 | Refresh while building answered 202 and screen follows build | `app/dossiers.py::refresh` (202 same body), `static/js/dossier.js` | S: refresh path returns 202 with same body; B: follow to ready |
| R2.149 | Uncertain outcome keeps key and body; success clears markers | `static/js/pending.js`, `home.js`, `dossier.js` | B: same key on retry (research); U: `tests/ui/pending.test.mjs` (4 tests pass); S: `test_lost_research_response_retry_replays_the_same_answer` and `test_refresh_retry_with_same_key_is_a_replay` replay the original answer |
| R2.150 | No background polling beyond building; no recovery across reloads | `static/js/dossier.js` | C |

## Not verified

- R2.84, R2.106, R2.107 (login, auth-error path)
- R2.101 contrast and focus (not measured)
- R2.131 refused refresh
- R2.142 empty-contested visible state
- R2.123 absent researched-at
- R2.126 contested marker on the dossier screen
- R2.145 (no requirement)
- R2.146 and R2.150 (code only)
- Timing of the 2 s poll (R2.136)
- Latest-read-wins in a browser (R2.147), covered only by the unit test
