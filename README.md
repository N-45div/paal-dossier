# Dossier

A containerised HTTP service that researches companies by web domain and keeps a
**dossier** for each: six fields (`legal_name`, `hq_city`, `ceo`, `founded_year`,
`headcount_range`, `funding_total`), each with the value the web supports and the
excerpts it came from. Builds run in the background, are read any number of times
and are refreshed on request. All web access goes through the Python package
`webrouter` (Nimble by default, Tavily optional) and costs at most 80 units per build.

## Layout

| Path | Contents |
|---|---|
| `stage-1/` | The deliverable for stage 1: `Dockerfile`, `RUN.md`, `requirements.txt`, `app/` (HTTP API, state, idempotency, export/import), `app/research/` (research engine), `tests/` (unit tests) |
| `stage-N/` | Later stages follow the same shape |
| `acceptance/stage-N/` | Independent black-box acceptance tests, run against a built image and the mock web |
| `mandates/` | The working rules of each seat that built this repository |

Inside `stage-1/app/research/`: `support.py` and its helpers implement the support rule
of the specification's Appendix A; `build.py`, `gateway.py`, `budget.py`, `decide.py`
and `evidence.py` run a build (search, extract, research, field decision).

## Build and run stage 1

`stage-1/RUN.md` is authoritative. In short, from `stage-1/`:

```sh
docker build -t dossier .
docker run --rm -e PORT=8080 -p 8080:8080 \
  -e NIMBLE_API_KEY=<key> -e NIMBLE_BASE_URL=<url> \
  -e TAVILY_API_KEY=<key> -e TAVILY_BASE_URL=<url> dossier
curl localhost:8080/health
```

Against the local mock web (`challenges/dossier/web` of the event repository), put both
containers on one Docker network, start the mock with
`-e MOCK_ADMIN_TOKEN=<token> -v <corpus dir>:/data/corpus:ro`, and point the service at
`http://<mock>:8080/nimble` and `http://<mock>:8080/tavily` with any non-empty keys.
Leave `NIMBLE_BASE_URL` unset only for a live run, which spends real units.

## Tests

```sh
pip install pytest pytest-asyncio httpx "webrouter[search,extract,research]>=0.12.0"
cd stage-1
python -m pytest tests/research -c tests/research/pytest.ini   # research engine
python -m pytest tests/api                                     # HTTP API
```

The acceptance suite is described in `acceptance/stage-1/README.md`.
