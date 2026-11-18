# Dossier service — run instructions

Build and start (from the `stage-1/` folder):

```sh
docker build -t dossier . && docker run --rm -e PORT=8080 -p 8080:8080 \
  -e NIMBLE_API_KEY=... -e NIMBLE_BASE_URL=... \
  -e TAVILY_API_KEY=... -e TAVILY_BASE_URL=... dossier
```

`GET /health` answers `200 {"status":"ok"}` once the service is up. Only `PORT`
(default `8080`) is required; the provider variables are read when a build runs.

## Layout

- `app/main.py` — ASGI app assembly, error handling.
- `app/routes/` — HTTP handlers (`control`, `auth`, `dossiers`).
- `app/store.py`, `app/dossiers.py`, `app/idempotency.py`, `app/snapshot.py` — in-memory state, dossier model, idempotency keys, versioned export/import; one event loop, mutations are synchronous sections.
- `app/builds.py` — background build orchestration; calls `app.research.run_build` (stub until present).
- `app/clock.py` — the injectable clock moved only by reset and `POST /_test/clock`.
- `app/domains.py` — domain normalisation and validation.
- `app/passwords.py` — scrypt password hashing (versioned format).
- `tests/api/` — unit tests (`pip install pytest httpx` then `pytest tests/api` from `stage-1/`).
- `tests/load/` — `CORPUS_DIR=<sample corpus> tests/load/run_load.sh [seconds] [fake]` (PYTHON=a python with httpx): 50-way mixed load against the container (2 CPUs, 3 GiB) with the mock web; asserts max latency < 5 s, no 5xx, reset < 10 s.
