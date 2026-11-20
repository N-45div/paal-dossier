# Running the Dossier service (Stage 1)

The service is a single container. It needs only Docker; no manual setup.

## Build and start

Run these from the repository root (the directory that contains `stage-1/`):

```sh
docker build -t dossier-service stage-1
docker run --rm -d --name dossier-service -e PORT=8080 -p 8080:8080 dossier-service
```

Check that it is up:

```sh
curl -s http://localhost:8080/health
```

The answer is `{"status":"ok"}`. Stop the container with:

```sh
docker stop dossier-service
```

## Environment

| Variable | Meaning |
|---|---|
| `PORT` | Port to listen on inside the container (default `8080`) |
| `NIMBLE_API_KEY`, `NIMBLE_BASE_URL` | Credentials and endpoint for the `nimble` provider |
| `TAVILY_API_KEY`, `TAVILY_BASE_URL` | Optional credentials and endpoint for the `tavily` provider |

The service reads the provider variables when it starts a build (Stage 1 builds that
need them are added with the research engine). The health and account endpoints need
none of them.

## Notes

- State is held in memory. Restarting the container clears it.
- The `/_test/*` control endpoints are enabled in this image and need no authentication.
