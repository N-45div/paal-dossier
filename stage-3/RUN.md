# Dossier service — run instructions (stage 3)

Everything the service needs is inside the image. Build and start it from the `stage-3/` folder:

```sh
docker build -t dossier-stage3 .
docker run --rm -p 8080:8080 -e PORT=8080 dossier-stage3

To keep state across a stop, start a named container without `--rm` and restart it with `docker start`:

```sh
docker run -d --name dossier-stage3 -p 8080:8080 -e PORT=8080 dossier-stage3
docker stop dossier-stage3 && docker start dossier-stage3
```
```

The image name `dossier-stage3` in these examples is a free choice: use any name, and use the
same name in the `docker run` line.

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
  dossier-stage3
```

Leave `NIMBLE_BASE_URL` unset to use the live Nimble endpoint, or set it to the provider
base URL. Never pass a variable as an empty string.

## Browser UI

The UI is served by the same process. Open <http://localhost:8080/> for the dossier list and
research form, `/signup`, `/login`, and `/dossiers/{domain}`. Pages are server-rendered HTML with
a small vanilla-JS layer and a local stylesheet under `/static/`; nothing is fetched from a CDN.
The browser keeps its session token in `localStorage`. `/dossiers/{domain}` answers HTML only to
`Accept: text/html`; other clients get JSON.

## Researching a domain

`POST /dossiers` starts a build and needs two headers: a bearer token and an `Idempotency-Key`
of 1 to 255 characters. Without the key the request is refused with 400
`missing_idempotency_key`; without a valid token it is refused with 401 `unauthenticated`.
Sign up for a token (201 on first use; 409 `email_taken` if the email is already registered, in
which case use `POST /auth/login` with the same `email` and `password`), then start the build:

```sh
TOKEN=$(curl -s -X POST http://localhost:8080/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email": "a@example.com", "password": "correct horse", "display_name": "Ada"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')

curl -s -X POST http://localhost:8080/dossiers \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Idempotency-Key: demo-1' \
  -H 'Content-Type: application/json' \
  -d '{"domain": "acme-robotics.test"}'
```

The first request answers 202 with `dossier_id`, `domain` and `state` (`building`). Repeating
the same request with the same `Idempotency-Key` and body answers 200 with the original body.
Fetch the result with `GET /dossiers/acme-robotics.test` (bearer token required).

## Ports and state

- The service listens on `0.0.0.0:$PORT` (default `8080`).
- State is durable on the container filesystem, in `$DOSSIER_DATA_DIR` (default `/srv/dossier/data`,
  file `state.json`). It survives a stop and a restart of the same container (`docker start`). With `--rm` the
  container is removed on stop, so its state is removed too; mount the path as a volume to keep it.
- A build running at the moment of an abrupt stop is recorded as `failed` after the restart.
- `POST /_test/reset` replaces all state with a fixture, `POST /_test/clock` moves the clock.

## Tests

The unit tests run without Docker from the `stage-3/` folder, with `aiohttp` installed:

```sh
pip install "aiohttp>=3.9,<4"
python -m unittest tests.service.test_skeleton tests.service.test_ui
```
