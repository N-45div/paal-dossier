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
seat waited for the Claude Pro usage window to reset. Model spend for all four stages was
**$56.15 at Anthropic list prices**: 601 M tokens, 97% of them cache reads, measured from the
seats' own session logs. The run itself was paid for by one Claude Pro subscription. The table in
[FACTORY.md](FACTORY.md#measured-cost-and-time) breaks this down by stage.

**Research economy.** On the kickoff's sample mock web, frozen stage 4 found all 48 of 48
fields for the six companies with an answer key, at **5.62 Nimble units per correct field**.
The units come from the mock's own priced call log, and the service's self-reported spend
matched it to the unit. Those six companies have no traps; on harder cases the service does
worse. See [FACTORY.md](FACTORY.md#research-economy-measured-on-the-sample-mock-web).

**What it got wrong.** FACTORY.md has a section on what the band missed, and why. In short:
- A ruling wrongly waived browser-rendered page text, so four sample companies return a stale
  value.
- A batch with a tight budget returns nothing.
- Earlier folders' tests and ledgers were touched minutes after the next specification was
  open.

It also lists everything that ran outside the room during the run: restarts, the usage-limit
guard, and live checks. See [What the factory missed](FACTORY.md#what-the-factory-missed-and-why)
and [the operator and automation log](FACTORY.md#operator-and-automation-log-run-6).

## Where Nimble is used

- **Nimble is the service's only research provider,** called through WebRouter
  (`stage-4/app/gateway.py`). Each build:
  1. Starts one Nimble research run with a structured schema.
  2. Runs five `lite` Nimble searches at the same time (1 unit each).
  3. Extracts the pages the searches found.
  4. Extracts the pages the research run cites.

  Every value the service returns quotes an excerpt from a page Nimble served.
- **Every call is paid for before it is sent.** The gateway reserves the call's cost against
  the build's 80-unit cap and the batch budget. A call Nimble refuses costs nothing, and a 429
  is retried after at least 1.05 seconds, up to four attempts.
- **Measured, not guessed:**
  - On the mock: 43 to 49 units per company, 5.62 per correct field.
  - On the live web: the stage 4 build researched 15 real companies through Nimble's live API
    (table below), at 52 to 59 units each. Every build finished `ready`, even while Nimble's
    extract endpoint returned HTTP 500s.
- **`dossier-runway.com.json`** is a live Nimble build of `stage-4/`, saved verbatim.

## Where Band is used

- **One Band Desktop room holds the whole run:** the dispatch, every handoff, verdict,
  rejection, ruling and freeze, between five seats. Its full session is committed unedited
  as `room.json`.
- **Seats reach each other only by `@` mention,** so every handoff carries the whole task:
  957 seat-to-seat mentions across 20 seat pairs, against a single message from the human.
- **The Git history is the seats' own,** pushed without amending, rebasing or squashing.
  Everything reached `main` through the Gatekeeper's merges. Commits per seat and lines per
  seat are in [FACTORY.md](FACTORY.md#teamwork-evidence).

## Where Cognee is used

- **Cognee Cloud is the factory's shared memory** (dataset `paal-org-brain`, over MCP).
  Before the run it held the lessons of runs 1 to 5, and the Lead recalled them at its first
  step.
- **A memory scribe copied every decision from the room as it happened:** 136 verdicts,
  rulings and freezes. The memory now answers questions about the run; see
  [Ask the memory](#ask-the-memory) below.
- **The live-web findings are stored there too,** so the next run starts from what the real
  web got wrong.

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

## Live research: stage 4 on the real web

After the freeze, the stage 4 build researched 15 real companies through Nimble. Ground
truth is public knowledge as of 2026. ✔ means right, ✘ wrong, · not found.

| Company | CEO | HQ city | Founded | Fields filled |
|---|---|---|---|---|
| runway.com | ✔ Anastasis Germanidis (co-CEO) | · | ✘ 2023 | 5/8 |
| stripe.com | ✔ Patrick Collison | ✔ San Francisco | ✔ 2010 | 7/8 |
| notion.so | ✔ Ivan Zhao | ✔ San Francisco | ✔ 2013 | 8/8 |
| openai.com | ✔ Sam Altman | ✔ San Francisco | ✘ 2023 | 6/8 |
| anthropic.com | ✔ Dario Amodei | ✔ San Francisco | ✔ 2021 | 7/8 |
| figma.com | ✔ Dylan Field | ✘ London | ✘ 2025 | 4/8 |
| linear.app | ✘ Jori Lallo | · | ✔ 2019 | 6/8 |
| vercel.com | ✘ Benjamin Netanyahu | ✔ San Francisco | ✔ 2015 | 6/8 |
| databricks.com | ✔ Ali Ghodsi | ✔ San Francisco | ✔ 2013 | 6/8 |
| airbnb.com | ✔ Brian Chesky | ✔ San Francisco | ✔ 2008 | 7/8 |
| shopify.com | ✘ Andrew Left | ✘ Toronto | ✔ 2004 | 6/8 |
| canva.com | ✔ Melanie Perkins | ✘ Surry Hills (a Sydney suburb) | ✔ 2013 | 5/8 |
| perplexity.ai | ✔ Aravind Srinivas | ✔ San Francisco | ✘ 1994 | 5/8 |
| huggingface.co | · | · | ✔ 2016 | 1/8 |
| mistral.ai | ✔ Arthur Mensch | ✘ France | · | 4/8 |

**Totals:** CEO 11 of 15, HQ city 8 of 15, founding year 10 of 15, 83 of 120 fields filled.

**How far to trust a value:** the service marks each value `known` or `contested`. On the
three scored facts (CEO, HQ city, founding year):

| Marked | Right | Wrong |
|---|---|---|
| `known` | 13 | 1 |
| `contested` | 16 | 10 |

On those three facts, every wrong value but one was flagged `contested` and carries the
citation that misled it. For example, Vercel's "CEO" comes from a headline about its CEO's
photo with a head of state.

The other fields are weaker. Executives include role words read as names, such as Runway's
"CTO: Computer Science", marked `known`. Funding totals often come from the wrong round or
the wrong company. `dossier-runway.com.json` gets Runway's CEO right and is wrong or unknown
on the other base fields. [FACTORY.md](FACTORY.md#memory-and-live-research) lists the failure
patterns.

## Ask the memory

Cognee Cloud holds the run's decisions: the memory scribe copied 136 verdicts, rulings and
freezes from the room as they happened. Asked after the run, it answers from that record:

> **Why was a handoff rejected in stage 1, and how was it fixed?**
> Stage 1 had three rejections: PB failed the sentence-splitting rule for abbreviations
> such as "Ltd" and "AS"; it was fixed to end the sentence after those suffixes. PC was
> rejected twice, for a missing `on_spend` contract and missing re-exports, then for not
> being rebased on main; those were fixed before re-handoff.

> **What did the Lead rule about the budget test that failed only after the restart tests
> in stage 4?**
> The Lead ruled it was a test-isolation defect, not a product bug: the budget test
> inherited mock state from the restart tests. It was fixed by running the module last and
> draining and resetting the mock in teardown.

> **Which lessons from earlier runs shaped how the Gatekeeper reviews handoffs?**
> Give every handoff a clear verdict, citing the failing ledger requirement and evidence
> when rejecting. Build and test the exact commit from a fresh checkout. Review against
> binding coordinator rulings. Audit test coverage, including planted-defect checks.
> Void checks that overlap outages and rerun them on the exact commit.

> **What revision was stage 3 frozen at, and which checks passed?**
> Stage 3 was frozen at main `887079a`. Checks passed: the isolated event check (stages 1
> and 2 passed; stage 3 9/9), unit and service tests (411 passed), and the Prover suite
> (248 passed, 0 failed).

The first, second and fourth answers match the room log. The third comes from the lessons
of runs 1 to 5, which seeded the memory before this run.
