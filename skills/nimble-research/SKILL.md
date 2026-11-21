---
name: nimble-research
description: Set up and verify Nimble web research (search, extract, research agents) for a service or a live run, routed through WebRouter where required, while keeping the Nimble key out of agent rooms and repositories. Use when someone needs a Nimble API key checked, a live run against the real web, or Nimble wired into a service through the webrouter package.
---

# Nimble web research

Nimble serves live web search, page extraction and multi-step research runs. In a Band
factory the **service** the seats build may call Nimble; the **seats themselves never hold
the key**, because everything a seat runs is recorded in a room log that is often published.

## Get and store the key

Sign up at https://online.nimbleway.com/signup, then **Settings -> API Keys -> Create key**.
Store it hidden:

```bash
read -rs K; printf 'NIMBLE_API_KEY=%s\n' "$K" > ~/.nimble.env; chmod 600 ~/.nimble.env; unset K
bash "$KIT/setup/nimble-check.sh" runway.com     # one lite search, prints the top results
```

## Calling Nimble from a service

When a specification requires WebRouter, every provider call goes through the Python
`webrouter` package (module `web_router`), in process or from a Python helper inside the
same container:

```text
pip install "webrouter[search,extract,research]>=0.12.0"
```

WebRouter's `nimble` provider reads `NIMBLE_API_KEY` and `NIMBLE_BASE_URL` from the
environment. Leave `NIMBLE_BASE_URL` unset (or set it to `https://sdk.nimbleway.com`) for the
live web; **an empty value counts as set** and every call fails with a missing-protocol error.
For offline tests, point it at a local mock instead.

## Cost and speed

- Depth `lite` (title, URL, snippet) is the cheapest search; `fast` adds a truncated body;
  `deep` returns the full page. Extract is billed per URL requested, research runs per start.
- Live calls are slow: a search can take over ten seconds and a research run about a minute.
  Services must not give up on a call too early.
- Spend per correct answer, not per call, is what to optimise: cheap lite searches to find
  candidate pages, then extract only the pages most likely to state the fact.

## A live run you start yourself

```bash
set -a; . ~/.nimble.env; set +a
docker run -d --name live -p 8000:8000 -e PORT=8000 -e NIMBLE_API_KEY \
  -e NIMBLE_BASE_URL=https://sdk.nimbleway.com <image>
```

Pass `-e NIMBLE_API_KEY` by name so the value never appears on the command line. Remove the
container (`docker rm -f live`) when done.
