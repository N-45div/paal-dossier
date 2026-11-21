# Dossier service — run instructions (stage 2)

Everything the service needs is inside the image. Build and start it from the `stage-2/` folder:

```sh
docker build -t dossier-stage2 .
docker run --rm -p 8080:8080 -e PORT=8080 dossier-stage2
```

Then check it:

```sh
curl -s http://localhost:8080/health      # {"status": "ok"}
```

## Provider configuration

The provider variables are passed at run time. Nimble is the default provider and is required
for research; Tavily is optional.

```sh
docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e NIMBLE_API_KEY=<key> \
  -e TAVILY_API_KEY=<key> \
  -e TAVILY_BASE_URL=<tavily endpoint> \
  dossier-stage2
```

Leave `NIMBLE_BASE_URL` unset to use the live Nimble endpoint, or set it to the provider
base URL. Never pass a variable as an empty string.

## Browser UI

The UI is served by the same process. Open <http://localhost:8080/> for the dossier list and
research form, `/signup`, `/login`, and `/dossiers/{domain}`. Pages are server-rendered HTML with
a small vanilla-JS layer and a local stylesheet under `/static/`; nothing is fetched from a CDN.
The browser keeps its session token in `localStorage`. `/dossiers/{domain}` answers HTML only to
`Accept: text/html`; other clients get JSON.

## Ports and state

- The service listens on `0.0.0.0:$PORT` (default `8080`).
- All state is in memory and is lost when the container stops.
- `POST /_test/reset` replaces all state with a fixture, `POST /_test/clock` moves the clock.

## Tests

The unit tests run without Docker from the `stage-2/` folder, with `aiohttp` installed:

```sh
pip install "aiohttp>=3.9,<4"
python -m unittest tests.service.test_skeleton tests.service.test_ui
```
