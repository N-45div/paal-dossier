# Paal — Dossier

**Team:** N Divij (solo, remote, India) · **Track:** Dossier · **Factory:** [Paal](https://github.com/N-45div/Paal), five Band seats

This repository is everything one dispatch produced. Five agent seats in one Band room
received the challenge, then planned, built, tested, reviewed and merged all four stages.
After that single message, no person wrote, edited or steered anything in the room. Every
line under `stage-1/` to `stage-4/` came out of the room log in `room.json`.

## Result

| Stage | Frozen (UTC, 2026-11-21) | Event harness, isolated mode |
|---|---|---|
| 1 | 05:44 | pass |
| 2 | 07:33 | pass, stage 1 regression pass |
| 3 | 12:43 | pass, stages 1–2 regressions pass |
| 4 | 17:30 | pass, stages 1–3 regressions pass |

`python -m harness run --track dossier --all` prints `claimed stage: 4`, and each
`stage-N/` folder claims its own stage. The dispatch went out at 05:07 UTC and stage 4
froze at 17:30 UTC. That was about 5 hours of seat work; for the rest of the time, every
seat waited for the Claude Pro usage window to reset. The table in
[FACTORY.md](FACTORY.md#measured-cost-and-time) breaks this down by stage.

## How to read this repository

| Path | What it is |
|---|---|
| [FACTORY.md](FACTORY.md) | The factory: seats, one stage end to end, how bad work is caught, design choices and their cost, failure handling, measured time, and what we tried that failed |
| [mandates/](mandates/) | One mandate per seat (Lead, Builder A, Builder B, Prover, Gatekeeper), each opening with its harness, model and effort |
| `room.json` | The full room session, downloaded from Band unchanged |
| `stage-1/` … `stage-4/` | One complete service per stage; each has its own `Dockerfile`, `RUN.md` and `LEDGER.md` (the numbered requirements and who satisfied each one) |
| [dossier-runway.com.json](dossier-runway.com.json) | `GET /dossiers/runway.com` from `stage-4/` built against the live web with Nimble, saved verbatim |
| [DISPATCH.md](DISPATCH.md), [SETUP.md](SETUP.md), `setup/`, `skills/`, `brain/` | The factory kit used to stand the band up, so the run can be repeated |

## The band

| Seat | Harness | Model | Job |
|---|---|---|---|
| Lead | Claude Code | claude-sonnet-5-5 | Turns the spec into a numbered ledger, splits it into packages, rules on disputes, freezes stages |
| Builder A, Builder B | Claude Code | claude-haiku-5-5 | Build disjoint packages in their own git worktrees and hand off commits |
| Prover | Claude Code | claude-haiku-5-5 | Writes black-box acceptance tests from the spec alone, never from the code |
| Gatekeeper | Claude Code | claude-sonnet-5-5 | Rebuilds each handoff from a clean checkout, runs every check, plants defects to test the tests, then accepts and merges or rejects with evidence |

The seats share memory through Cognee Cloud: lessons from earlier runs, plus every verdict
and ruling as the run made it. Live research for real companies goes through Nimble only
after a stage is frozen, so no seat ever holds a live key. Both are described in
[FACTORY.md](FACTORY.md#memory-and-live-research).
