# Dossier service — run instructions (stage 1)

Everything the service needs is inside the image. Build and start it from the `stage-1/` folder:

```sh
docker build -t dossier-stage1 .
docker run --rm -p 8080:8080 -e PORT=8080 dossier-stage1
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
  dossier-stage1
```

Leave `NIMBLE_BASE_URL` unset to use the live Nimble endpoint, or set it to the provider
base URL. Never pass a variable as an empty string.

## Ports and state

- The service listens on `0.0.0.0:$PORT` (default `8080`).
- All state is in memory and is lost when the container stops.
- `POST /_test/reset` replaces all state with a fixture, `POST /_test/clock` moves the clock.

## Tests

The unit tests run without Docker from the `stage-1/` folder, with `aiohttp` installed:

```sh
pip install "aiohttp>=3.9,<4"
python -m unittest tests.service.test_skeleton
```
