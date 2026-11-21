---
name: band-factory
description: Set up and run a multi-agent software factory in Band Desktop - install Band Desktop, Claude Code and Codex on Linux/WSL2, create five agent seats (Lead, Builder A, Builder B, Prover, Gatekeeper) with generic mandates, prepare a worktree-per-seat result repository, open a room and send the single dispatch message. Use when someone asks to set up Band agents, a dark factory, an agent team, or to run a specification through Band seats.
---

# Band factory

Stand up the Paal factory on a Linux or WSL2 machine. The kit root is the directory that
holds `mandates/`, `setup/` and `DISPATCH.md` (call it `$KIT`); the workspace is `$WS`
(default `~/buildathon`).

## Rules that always apply

- Never write keys into a repository, a mandate, a room message or a command that echoes
  them. Ask the person to type keys at a hidden prompt (`read -rs`) into `chmod 600` files.
- Never write the product code yourself when the person intends the seats to build it.
  Your job is the factory: machine, seats, repository, room and dispatch.
- After the dispatch, do not post in the room unless the person says this is a practice run.

## 1. Check the machine

```bash
docker run --rm hello-world >/dev/null && echo docker ok
band doctor            # every line [ok]; if missing, install Band Desktop (SETUP.md §6)
claude --version; codex --version
```

On Windows, everything runs inside WSL2 (SETUP.md §1). Missing tools: run
`bash $KIT/setup/bootstrap-user.sh "$WS" "$KIT"` as the normal user, then as root
`$WS/sf-buildathon-2026/.venv/bin/python -m playwright install-deps chromium` if browser
checks are needed.

## 2. Sign the runtimes in

- Claude Code: `claude` then `/login`, or an API key through `apiKeyHelper` in
  `~/.claude/settings.json` pointing at a script that prints a `chmod 600` key file.
- Codex: `read -rs K && printf %s "$K" | codex login --with-api-key; unset K`.
- Band Desktop launches programs without your shell profile: make sure `claude` and `codex`
  resolve from `/usr/local/bin` (a wrapper that sets PATH for nvm installs).

## 3. Band Desktop settings (Settings -> Runtime)

Human approval wait: deny after 5 minutes. Question timeout: 300 s. Room activity feed: tool
calls. Stop idle agents after: 1800 s. Integrations: Claude Code and Codex on.

## 3b. Optional: shared memory and web research

- Shared memory for all seats: follow the `cognee-memory` skill (`setup/cognee.sh local` or
  `cloud`). Seats must inherit user MCP servers to see it.
- Web research for the service being built: follow the `nimble-research` skill. Keep the
  Nimble key with the person, never with a seat.

## 4. Create the seats

```bash
cd "$WS" && DRY_RUN=1 bash "$KIT/setup/create-seats.sh" rehearsal   # Codex probes must pass
bash "$KIT/setup/create-seats.sh" rehearsal                           # or: judged
band list                                                             # five peers, Connected
```

Claude Code dry-run probes report Band's relay as failed because no real seat exists yet;
that is expected. Then copy each seat's real model id and effort into the `Model:` and
`Effort:` lines of its mandate.

## 5. Repository, room, dispatch

```bash
bash "$KIT/setup/prepare-result-repo.sh" "$WS/band-work/result"
band chat new --as <owner>/lead --with <owner>/builder-a --with <owner>/builder-b \
  --with <owner>/prover --with <owner>/gatekeeper --with <owner>     # prints the room id
band room participants <room-id>                                      # note the Lead's id
band room send <room-id> "$(cat dispatch.md)" --mention <lead-participant-id>
```

Write `dispatch.md` from `$KIT/DISPATCH.md`: absolute paths, worktrees, port ranges per
seat, the specification files in order, and the check commands.

## 6. Watch without steering

```bash
band room messages <room-id>          # newest messages
band usage                            # token use and estimated cost per coding agent
```

In a practice room you may intervene and then edit the mandates. In a submitted run, the
dispatch is the only human message.
