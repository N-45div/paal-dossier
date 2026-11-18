# Dossier service — run instructions

From the `stage-1/` folder, build the image and start the service (two commands):

```sh
docker build -t dossier .
docker run --rm -e PORT=8080 -p 8080:8080 \
  -e NIMBLE_API_KEY=<key> -e NIMBLE_BASE_URL=<nimble base url> \
  -e TAVILY_API_KEY=<key> -e TAVILY_BASE_URL=<tavily base url> dossier
```

`GET http://localhost:8080/health` answers `200 {"status":"ok"}` within a few seconds.

| Variable | Meaning |
|---|---|
| `PORT` | Port to listen on, default `8080`; the `-p` mapping must use the same port |
| `NIMBLE_API_KEY` | Credential for the `nimble` provider (required for research) |
| `NIMBLE_BASE_URL` | Nimble endpoint; leave it **unset** for the live service (an empty value counts as set) |
| `TAVILY_API_KEY`, `TAVILY_BASE_URL` | Optional second provider; research works with Nimble alone |

The provider variables are read when a build runs; the service starts without them.
Everything runs in the one container, in memory; no volume, database or compose file is needed.

## Layout

- `app/main.py` — ASGI app assembly and uniform error handling; `app/__main__.py` starts uvicorn.
- `app/routes/` — HTTP handlers (`control`, `auth`, `dossiers`).
- `app/store.py`, `app/dossiers.py`, `app/idempotency.py`, `app/snapshot.py` — in-memory state, dossier model, idempotency keys, versioned export/import. One event loop; every mutation is a synchronous section.
- `app/builds.py` — background builds on one shared engine-loop thread; calls `app.research.run_build`, applies results only if no reset/import happened meanwhile.
- `app/research/` — the research engine (WebRouter calls, Appendix A support rules, field decisions).
- `app/clock.py`, `app/domains.py`, `app/passwords.py` — injectable clock, domain normalisation, scrypt hashing (versioned format).
- `tests/api/` — service unit tests; `tests/research/` — engine unit tests (`pip install -r requirements.txt pytest pytest-asyncio httpx`, then `python -m pytest tests/api`).
- `tests/load/` — `CORPUS_DIR=<sample corpus> PYTHON=<python with httpx> tests/load/run_load.sh [seconds] [fake]`: 50-way mixed load on the container (2 CPUs, 3 GiB) with the mock web.
