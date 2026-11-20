# Running the Dossier service (stage 1)

Requires Docker. Nothing else is installed by hand: the image installs Python 3.12,
`webrouter[search,extract,research]>=0.12.0` and the service itself.

## Build and start

```sh
docker build -t dossier-stage-1 stage-1
docker run --rm -p 8080:8080 -e PORT=8080 \
  -e NIMBLE_API_KEY=<your-nimble-key> \
  -e NIMBLE_BASE_URL=<nimble-base-url-or-omit> \
  dossier-stage-1
```

`PORT` selects the listening port inside the container (default 8080); map it with `-p`.
`NIMBLE_BASE_URL` may be omitted to use the live Nimble endpoint. Tavily variables
(`TAVILY_API_KEY`, `TAVILY_BASE_URL`) are optional and are not needed for stage 1.

Check that it is up:

```sh
curl http://localhost:8080/health
```

## Testing against the mock web

```sh
docker build -t dossier-web challenges/dossier/web
docker network create dossier
docker run --rm -d --name web --network dossier -e MOCK_ADMIN_TOKEN=local-admin \
  -v "$PWD/challenges/dossier/web/corpus/sample:/data/corpus:ro" dossier-web
docker run --rm --network dossier -p 8000:8000 -e PORT=8000 \
  -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://web:8080/nimble \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://web:8080/tavily \
  dossier-stage-1
```

## Tests

The unit tests run in the host Python (3.12) against an in-process server:

```sh
cd stage-1
python -m pip install -r requirements.txt pytest
PYTHONPATH=. python -m pytest tests -q
```
