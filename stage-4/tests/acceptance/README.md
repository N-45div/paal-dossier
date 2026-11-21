# Stage 1 acceptance suite (Prover)

Black-box tests written from `stage-1.md` (sections 1-11 and Appendix A) and the mock web
README. They use only the service's HTTP interface and the mock's admin API. No builder
source is read. Owner: `@prover`.

## Files

| File | Covers |
|---|---|
| `oracle.py` | Independent Appendix A oracle, page/header split, excerpt rules (R1.94-R1.120, R1.257-R1.310) |
| `test_oracle_selfcheck.py` | Oracle against the spec's own examples (no service) |
| `test_spec_clauses.py` | Appendix A tables, cost table, clock, field shape, export/import edge rules |
| `test_a_fresh_clock.py` | Clock follows system time before the first reset (must run first, fresh container) |
| `test_contract_http.py` | Health, reset, clock, errors, auth, query validation, no 5xx |
| `test_idempotency.py` | Idempotency matrix, concurrent identical and conflicting requests, refresh |
| `test_dossier_build.py` | Builds against the mock: fields, citations, support, budget, search rule, faults, list, reset |
| `test_snapshots_and_bursts.py` | Export/import, snapshot during a build, bursts, budget under concurrency |
| `coverage.py` | Which ledger ids are named by a test; prints the uncovered ones |
| `run_suite.sh` | Builds the stage-1 image and the mock, runs the suite, removes what it started |

## Run

Full run (builds the service from `stage-1/`, starts the mock with the sample corpus, runs
pytest, then removes its containers; ports 18210 and 18220; held under
`/tmp/factory-heavy.lock`):

```sh
stage-1/tests/acceptance/run_suite.sh
```

Against a service and mock you already run:

```sh
pip install -r stage-1/tests/acceptance/requirements.txt
cd stage-1/tests/acceptance
BASE_URL=http://127.0.0.1:18210 MOCK_URL=http://127.0.0.1:18220 MOCK_ADMIN=local-admin \
  python3 -m pytest -p no:cacheprovider
```

Environment:

| Variable | Default | Meaning |
|---|---|---|
| `BASE_URL` | `http://127.0.0.1:18210` | The service under test |
| `MOCK_URL` | `http://127.0.0.1:18220` | The mock web (admin API used for call logs, faults, epochs) |
| `MOCK_ADMIN` | `local-admin` | The mock's `MOCK_ADMIN_TOKEN` |
| `SAMPLE_DOMAINS` | three sample-corpus domains | Companies the build tests research (must exist in the mock corpus) |

The mock is required. Tests fail (not skip) when it is unreachable.

Ledger coverage:

```sh
python3 stage-1/tests/acceptance/coverage.py <path to LEDGER.md>
```

## Conventions

- Each test names the ledger ids it checks in its docstring or a comment (`R1.nnn`).
- Money and provider cost are read from the mock's call log, never from the service.
- The `run_suite.sh` run is the only place that starts containers. It names every container
  and network with the `prover-stage1-` prefix and removes them on exit.
- Tests must not be weakened to make a revision pass. A disputed expectation goes to `@lead`
  with the spec clause.

## Known gaps (not testable by this suite as written)

See the `STRUCTURAL` table in `coverage.py`. Those ids are checked by the build and the
gatekeeper's review, not by a request: the packaging rules, the provider routing rule, the
resource limits, and the restart rule.
