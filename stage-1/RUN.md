# Dossier service — run instructions

Build and start (from this folder, `stage-1/`). The command is complete as written; the five
provider variables are passed through from your shell and are simply left out of the container
when they are not set:

```sh
docker build -t dossier . && docker run --rm -p 8080:8080 -e PORT=8080 \
  -e NIMBLE_API_KEY -e NIMBLE_BASE_URL -e TAVILY_API_KEY -e TAVILY_BASE_URL dossier
```

`GET /health` answers `{"status":"ok"}` within a few seconds. `PORT` defaults to 8080.

- `NIMBLE_API_KEY` is needed for research; leave `NIMBLE_BASE_URL` unset to use the live Nimble endpoint.
- `TAVILY_API_KEY` and `TAVILY_BASE_URL` are optional; without them research uses Nimble only.

Layout: `app/` is the service (Python 3.12, Starlette on a single uvicorn worker, all state in
memory); `app/research/` is the research engine behind `app.research.run_build`;
`tests/api/` holds the API unit tests (`pip install pytest httpx`, then `pytest tests/api`).

## Integration harness (not part of the image)

`tools/` builds the image and the mock web on private docker names (`builder-a-*`, ports
18010/18011, builds under `flock /tmp/factory-heavy.lock`):

- `python3 tools/corpus_table.py [--no-build] [--no-tavily] [company.test ...]` builds every sample
  company and prints units per build (mock log vs `spent_units`), wall time and each field against
  the key's `expected["1"]["0"]`; exit code 1 on any problem.
- `python3 tools/checks.py [startup] [load] [faults]` measures start-to-healthy under
  `--cpus 2 --memory 3g`, runs 50 requests in flight, and injects provider faults.
- Env: `HARNESS_HANDLE`, `HARNESS_SERVICE_PORT`, `HARNESS_MOCK_PORT`, `MOCK_WEB_DIR`, `MOCK_CORPUS_DIR`.
