# Dossier service — run instructions

Build and start (from this folder, `stage-1/`):

```sh
docker build -t dossier . && docker run --rm -p 8080:8080 -e PORT=8080 \
  -e NIMBLE_API_KEY=... -e NIMBLE_BASE_URL=... \
  [-e TAVILY_API_KEY=... -e TAVILY_BASE_URL=...] dossier
```

`GET /health` answers `{"status":"ok"}` within a few seconds. `PORT` defaults to 8080.
Leave `NIMBLE_BASE_URL` unset to use the live Nimble endpoint.

Layout: `app/` is the service (Python 3.12, Starlette on a single uvicorn worker, all state in
memory); `app/research/` is the research engine behind `app.research.run_build`;
`tests/api/` holds the API unit tests (`pip install pytest httpx`, then `pytest tests/api`).
