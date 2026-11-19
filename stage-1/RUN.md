# Dossier service, stage 1

The service is one container. It listens on `PORT` (default 8080) and needs no other setup.

## Build

Run these commands from the `stage-1` folder:

```sh
docker build -t dossier-stage1 .
```

## Run

```sh
docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e NIMBLE_API_KEY -e NIMBLE_BASE_URL \
  -e TAVILY_API_KEY -e TAVILY_BASE_URL \
  dossier-stage1
```

The `-e NAME` flags pass each provider variable from your shell into the container. Leave
`NIMBLE_BASE_URL` and `TAVILY_BASE_URL` unset to use the live providers. Set them only to point
the service at a different endpoint.

Check that it is up:

```sh
curl -s http://localhost:8080/health
```

The response is `{"status": "ok"}`.
