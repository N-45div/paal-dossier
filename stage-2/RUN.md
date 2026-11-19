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

## Development harness

The measurement harness (image build, mock web, corpus table, load and fault checks) is a development
aid and is not part of this folder; it lives on git branch `builder-a` under `stage-1/tools/`.
