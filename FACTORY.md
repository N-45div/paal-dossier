# The Ledger Factory

A five-seat software factory for Band Desktop. It turns a written specification into a
numbered **requirements ledger**, builds against it in parallel, tests each requirement with
tests written from the specification rather than the code, and lets only reviewed work reach
the integration branch. Nothing in the mandates names a problem domain: point the factory at a
different specification and it runs the same way.

This file describes the factory and the run we submit (run 6). It also reports what that
run got wrong, what ran outside the room while it worked, and the five earlier runs that
failed. Every number here comes from the room log, the Git history or a script in `setup/`.

## Run 6 at a glance

| | |
|---|---|
| Dispatch | One message, 2026-11-21 05:07:20 UTC. No other human message until the final report |
| Stages | 1 to 4 frozen at 05:44, 07:33, 12:43 and 17:30 UTC. The event harness in isolated mode passes all four on the frozen revision `4933316`, from a fresh clone |
| Time | 12 h 23 m from dispatch to final report, of which 7 h 18 m was waiting for the Claude Pro usage window. About 5 h of work |
| Model spend | $56.15 at Anthropic list prices (601 M tokens, 97% cache reads); paid for by one Claude Pro subscription |
| Research economy (sample mock web) | 5.62 Nimble units per correct field on the six sample companies with an answer key (48 of 48 correct). Weaker on harder cases; see [Research economy](#research-economy-measured-on-the-sample-mock-web) |

## Seats

| Seat | Harness | Model (effort) | Owns |
|---|---|---|---|
| Lead | Claude Code | claude-sonnet-5-5 (high) | Ledger, work packages, rulings, stage freeze, reports |
| Builder A | Claude Code | claude-haiku-5-5 (medium) | Implements assigned packages |
| Builder B | Claude Code | claude-haiku-5-5 (medium) | Implements assigned packages |
| Prover | Claude Code | claude-haiku-5-5 (medium) | Black-box acceptance tests derived from the specification |
| Gatekeeper | Claude Code | claude-sonnet-5-5 (medium) | Clean-checkout review, all check runs, planted defects, merges, final checks |

Mandates: [`mandates/`](mandates/). Each one says how a seat works, never what it builds. They
were last edited before the dispatch and are byte-identical to the factory kit's tag
`v1.4-judged`.

**One subscription, one model family.** Every seat runs on one Claude subscription: Sonnet
where judgement gates the work (Lead, Gatekeeper), Haiku where the work is well specified
(builders, Prover). Runs 1 to 5 put the Prover and Gatekeeper on other model families through
Codex, from run 4 on through [`setup/model-proxy.py`](setup/model-proxy.py). Runs 3, 4 and 5
each stopped when a third-party provider failed mid-run (quota, credit, or a model that could
not hold a long review); see [What we tried that failed](#what-we-tried-that-failed).

The cost of this choice is real. Test writer and builders share a model, and the tests live in
the shared repository. The Prover's independence is procedural only: its mandate says it
derives tests from the specification and never reads product code first. Nothing enforces
that. A sealed suite on a second model family would be stronger; see
[What we would build next](#what-we-would-build-next).

## One stage, end to end

```text
dispatch -> @lead reads the stage spec, writes the ledger (every "must" = one id, quoted verbatim)
         -> @builder-a + @builder-b build disjoint packages      } in parallel
         -> @prover writes tests per ledger id from the spec only }
         -> builder hands off a commit -> @gatekeeper: clean checkout, build, run, test, read diff
              REJECT (failing ids + evidence) -> builder fixes -> hands off again
              ACCEPT -> merge into main
         -> all packages in -> @gatekeeper final check (isolated) -> @lead freezes the folder,
            copies it forward and opens the next specification
```

## How it catches bad work

1. **The ledger.** Every normative sentence, table row and appendix rule becomes an id with
   the specification quoted. Work is assigned and accepted per package of ids. In practice
   the Lead kept the package table current but not the per-id status. In run 6's final
   ledger, 161 ids still read `[open]` while their packages read `accepted`.
2. **Tests from the specification.** The Prover derives expected behaviour from the
   specification and the dependency's documentation. Ledger ids named by at least one test,
   by stage:

   | Stage | Ids named by a test |
   |---|---|
   | 1 | 310 of 310 |
   | 2 | 104 of 160 |
   | 3 | 56 of 78 |
   | 4 | 64 of 68 |

3. **Clean-checkout review.** The Gatekeeper builds every handed-off commit from a fresh
   checkout and follows the run instructions literally. Uncommitted files, broken run
   instructions and nested repositories therefore fail before they reach `main`.
4. **Planted defects.** The Gatekeeper plants defects in a scratch copy to check that the tests
   catch them. In stage 4 it planted three, and the tests caught all three.
5. **Diff review.** The Gatekeeper rejects logic that branches on a check's inputs, weakened
   tests, changes to frozen folders, and credentials.
6. **Isolated final check.** Each stage ends with the event check in isolated mode, which
   catches dependencies on outbound network access.
7. **Loop guard.** An id rejected three times is re-planned by the Lead (split, reassigned or
   re-derived) instead of retried.

**Every rejection in run 6, and what it changed:**

| When (UTC) | Rejected | Reason | What came back |
|---|---|---|---|
| 05:17 | PB `2bc5260` (Builder B) | Sentence splitting broke on "Ltd." and "AS." | Fixed splitter and 163 unit tests; accepted 05:26 |
| 05:23 | PC `ac61e08` (Builder B) | Did not integrate with `main` | Rebased |
| 05:26 | PC `7588c1b` | Service did not start (`ImportError: FIELD_NAMES`) | Fixed, then accepted |
| 05:55 | Prover `faf680a` | Changed a file under frozen `stage-1/` | Not merged |
| 11:48 | Builder A `3114aa1` | 18 Prover tests failed (203 passed), among them Effective dates and duplicate feed entries | Fixed and handed off again |
| 12:27 | Stage 3 `main` `2bdb259` (final) | Event check 8 of 9: `learned_at` null in `GET /changes` | Fixed; stage 3 then passed 9 of 9 |
| 16:32 | Stage 4 head `80eb3a6` | Handoff claimed ledger ids no test named | Tests added, no product change |
| 16:33 | Builder B `7d2985f` | The same naming gap | Tests added, no product change |

Four of the eight changed product behaviour. The stage 3 final rejection came from the event's
shipped check after the band's own suite had passed. To write its regression test, the Prover
then read the shipped check, which its mandate says not to do.

## What the factory missed, and why

An independent review of the entry after the run found these. We report them because each
one points at a rule the factory needs.

- **Browser-rendered page text.** The stage 2 specification defines a page's text as the
  text a browser shows once the page has loaded. Ruling Rul-S2-4 (`stage-2/LEDGER.md:2073`)
  told the band that the mock serves the same text either way and not to use Nimble's
  `render`. That is false for four sample companies. Frozen stage 4 returns the extract-only
  value for all four:

  | Company | Field | Returned | The loaded page says |
  |---|---|---|---|
  | quillmate.test | hq_city | Brno | Manchester |
  | larkspur-health.test | hq_city | Austin | Plzen |
  | ferncliff-foods.test | ceo | Ingrid Brennan | Priya Castillo |
  | ostrava-mobility.test | legal_name | Ostrava Mobility Holdings s.r.o. | Ostrava Mobility s.r.o. |

  The Prover had marked the matching ids "not observable black-box", so no test challenged the
  ruling. The lesson: a ruling may settle an ambiguity, but it must never narrow a requirement
  without a test that proves the narrowing is safe.
- **Stage 1 import.** Ruling Rul-S2-2 imports one candidate per exported citation, because
  stage 1's export did not store the served page text. The specification asks for one
  candidate per supported value per page. A stage's export should keep everything a later
  stage could need.
- **A starved batch.** A three-company batch with a 40-unit budget spends all 40 units and
  returns no known field. Each build spends its first 25 units on a Nimble research run
  before any cheaper call. The band never measured spend per correct field during the run.
- **Earlier folders touched after the next specification was open.** At each stage boundary,
  the Lead opened the next specification a few minutes before the Gatekeeper merged the
  freeze. No product code changed: `git diff <frozen>..main -- stage-N/app` is empty for every
  stage.

  | Boundary | Next spec opened (UTC) | Last change to the earlier folder |
  |---|---|---|
  | 1 to 2 | 05:43:35 | 05:43:51 (Prover tests `16d46b5`), 05:44:58 (seed and ledger `f7568fc`) |
  | 2 to 3 | 07:33:30 | 07:35:34 (seed and ledger `36334b1`) |
  | 3 to 4 | 12:42:06 | 12:46:17 (`17395e8` edited a stage 3 test), 12:46:24 (`9a98131` restored it) |

- **`stage-4/RUN.md`** is still titled "(stage 3)" and tells the reader to build `stage-3/`.
  The Dockerfile in `stage-4/` is correct, and the harness builds that.
- **Git identity in extra worktrees.** Builder B made four stage 3 commits from an extra
  worktree that had inherited the repository's default identity, so Git shows them as
  "Gatekeeper": `1e3f9c8`, `4670803`, `683b8c5` and `433121d`. The room log at 07:36 to 07:46
  UTC shows Builder B making them.
- **Reports.** The Lead reported stage 1 and the final result to the person, but not stages 2
  and 3, although its mandate asks for a report at every freeze.

## Operator and automation log (run 6)

Nothing below posted in the room. It is listed because it ran while the band worked.

- **Restarts.**
  - [`setup/idle-restart.sh`](setup/idle-restart.sh) restarted all five seats 13 times when the
    room had been idle for 20 minutes. All but one fell inside a usage-limit pause, where
    nothing could run.
  - The exception was 11:46:25 UTC, which ended a 21-minute stall in stage 3 (11:25:38 to
    11:46:25) when no seat held a pending message.
  - [`setup/billing-guard.sh`](setup/billing-guard.sh) waited out three usage limits (06:01,
    07:47, 12:56) and restarted each seat after the reset.
  - A restart resumes a seat's own pending messages and open tasks; it sends nothing to the room.
- **One operator action on the guard.** At 06:18:47 UTC the operator relaunched the billing
  guard so it would always wait for the subscription instead of falling back to an API key.
- **Factory-kit changes during the run.**
  - Between 05:42 and 05:46 UTC the operator started
    [`setup/memory-scribe.py`](setup/memory-scribe.py) and committed it with
    [`setup/live-check.sh`](setup/live-check.sh).
  - At 13:42 UTC the operator committed a fix to `live-check.sh`.
  - No mandate changed.
- **Live checks.** After each freeze the operator ran `live-check.sh` against real companies.
  Its results were written to `band-work/live/`, a folder the seats could read. In stage 4,
  Builder B listed the folder and read its earlier `runway.com` results (16:23 UTC), and the
  Lead listed the folder (16:25 UTC). They contain the service's own earlier outputs, not any specification.
- **Leftovers from earlier runs.** The workspace still held earlier runs' folders. In stage 4
  the Gatekeeper used `run5-scratch/` and `run5-checks/` as scratch space for its own checks.
  A `git fetch` by Builder A at 05:19:56 UTC brought in the remote branch
  `backup/builder-b-04129542` from run 4. It appears only in branch listings; no seat checked it
  out or read a file from it.
- **The public repository keeps the earlier runs' tags.** `run1/*` to `run5/*` and that backup
  branch are kept on purpose as evidence for the section below. The judged run is `main`.
- **After the run.** On 2026-11-23 at 14:08 UTC, Builder A and the Prover each recorded one
  "no reply needed" on an old message when Band Desktop reconnected to download the room. They
  sent no text and made no commits. The last seat text message of the run is 17:30:40 UTC on
  2026-11-21.

## Memory and live research

**Shared memory (Cognee Cloud).** Every seat reaches one Cognee Cloud tenant over MCP
(`setup/cognee.sh cloud`), dataset `paal-org-brain`. Before a run it holds the retrospectives
of earlier runs. During a run, [`setup/memory-scribe.py`](setup/memory-scribe.py) copies every
verdict, ruling, freeze and blocker from the room into the same dataset every 20 minutes,
verbatim. The scribe only reads the room and writes memory; it never posts.

What run 6 did with it:

- **Seats:** two calls, both by the Lead. At its first step it recalled the lessons of runs 1
  to 5. When stage 1 froze it stored that stage's retrospective. No other seat called memory.
- **Scribe:** 17 batches, 136 decisions stored, from the first verdict to the final report.
- **After the run:** the dataset answers questions about the run. Asked which stage 4
  handoffs were rejected and why, it returned both commits and the reason.

Memory earned its place across runs, not within one. Inside a run, the room, the ledger and
Git were faster and exact.

**Live research (Nimble).** Seats never hold a live provider key, and every check in the run
uses the mock web. [`setup/live-check.sh`](setup/live-check.sh) builds a frozen folder and
researches real companies through Nimble, following the event guide's steps.
`dossier-runway.com.json` is its `runway.com` result for `stage-4/`, saved verbatim.

**Stage 4 on 15 real companies,** scored on three public, stable facts:

| Fact | Right |
|---|---|
| CEO | 11 of 15 |
| HQ city | 8 of 15 |
| Founding year | 10 of 15 |

- **Fields filled:** 83 of 120.
- **Cost:** 52 to 59 units and 58 to 150 seconds per company.
- **Every build ended `ready`,** even while Nimble's extract endpoint returned HTTP 500 errors.
- **Status was a useful signal on these three facts.** Values marked `known` were right 13
  times out of 14, and values marked `contested` 16 times out of 26.
- **The other fields are weaker.**
  - Executives include role words read as names, such as Runway's "CTO: Computer Science",
    marked `known`.
  - Funding totals are often from the wrong round or the wrong company.
  - `dossier-runway.com.json` gets the CEO right and is wrong or unknown on the other base
    fields.

The mistakes follow patterns the mock corpus does not contain:
- Headlines that put a famous name beside the company.
- Other dates (an incorporation, an acquisition, a birth year) read as the founding year.
- Regional offices read as the headquarters.
- Team-page layouts where a label sits next to the wrong name.

These findings are stored in `paal-org-brain` for the next run.

## Measured cost and time

Times come from the room's timestamps.

| Stage | Frozen (UTC) | Wall clock | Paused on the Pro limit | Working time |
|---|---|---|---|---|
| 1 | 05:44 | 0 h 37 m | none | 0 h 37 m |
| 2 | 07:33 | 1 h 49 m | 06:00 to 06:18 | 1 h 31 m |
| 3 | 12:43 | 5 h 10 m | 07:46 to 11:18 | 1 h 38 m |
| 4 | 17:30 | 4 h 47 m | 12:55 to 16:23 | 1 h 19 m |
| Total | | 12 h 23 m | 7 h 18 m | 5 h 05 m |

- **Result.** The event's harness in isolated mode passes stages 1 to 4 on the frozen revision,
  and each `stage-N/` folder claims its own stage. At the last freeze the band's own checks
  stood at:
  - 271 acceptance tests passed, 0 failed;
  - 519 unit and service tests;
  - 2 UI tests;
  - 18 of 18 restart scenarios.
- **Where the time went.** More than half the wall clock was waiting for the Pro 5-hour
  window. A plan without that limit would bring the run close to its 5 hours of work.
- **Model spend: $56.15 at Anthropic list prices,** measured from the seats' own Claude Code
  session logs with [`setup/spend.py`](setup/spend.py). The run was paid for by one Claude Pro
  subscription; the dollar figure is what the same tokens cost on the API.

  | Model (seats) | Requests | Tokens | List price |
  |---|---|---|---|
  | claude-sonnet-5-5 (Lead, Gatekeeper) | 1,045 | 147.0 M | $27.74 |
  | claude-haiku-5-5 (Builder A, Builder B, Prover) | 2,173 | 454.5 M | $28.41 |

  Haiku 5.5 bills a request whose prompt is over 100,000 tokens at its higher rate. 1,682 of the
  2,173 Haiku requests were over that line, so shorter seat contexts are the cheapest saving
  left.
- **Room volume.** `room.json` holds 7,003 messages:
  - 391 text messages;
  - 3,299 tool calls;
  - 3,295 tool results;
  - 13 errors, all of them Pro-limit notices;
  - 5 participant events.

  Band's API also returns about 2,590 task events that the download leaves out.

### Research economy, measured on the sample mock web

[`setup/economy-check.sh`](setup/economy-check.sh) builds a frozen stage and researches every
sample company that has an answer key. It resets the mock before each company and counts
units from the mock's own priced call log, not from what the service reports. On frozen
stage 4 (`4933316`):

| Company | Units | Correct fields |
|---|---|---|
| halvorsen-robotics.test | 49 | 8 / 8 |
| corvid-security.test | 44 | 8 / 8 |
| pemberton-analytics.test | 46 | 8 / 8 |
| mosaic-freight.test | 44 | 8 / 8 |
| windrush-bakery.test | 44 | 8 / 8 |
| ashgrove-solar.test | 43 | 8 / 8 |
| **Total** | **270** | **48 / 48** |

- **5.62 units per correct field,** with every field right on these six. All six are "plain"
  companies without traps. The rendered-text and tight-budget cases in
  [What the factory missed](#what-the-factory-missed-and-why) cost correct fields, so the
  judges' stage 4 workload will score lower.
- **Where the units go.** Per build: one Nimble research run (25 units), five `lite` searches
  (5 units) and 13 to 19 page extracts (1 unit each).
- **The service's own count is exact.** Its `spent_units` matched the mock's call log to the
  unit for every company.
- **Measured after the run by the operator,** not by the band.

### Teamwork evidence

Read from Git and `room.json`.

- **One human message:** the dispatch. The seats sent everything else.
- **The seats address each other directly:** 957 seat-to-seat `@` mentions across 20 seat
  pairs.

  | Seat | Text messages |
  |---|---|
  | Lead | 120 |
  | Gatekeeper | 72 |
  | Builder A | 69 |
  | Prover | 67 |
  | Builder B | 62 |

- **The work is spread across seats.** Lines added under `stage-*/` in non-merge commits on
  `main`. Builder B's four commits made under the "Gatekeeper" identity are credited to Builder
  B, and two spellings of a seat's name (`prover`, `builder-b`) are merged.

  | Seat | Product and docs | Tests | Ledger |
  |---|---|---|---|
  | Builder A | 4,083 | 2,758 | |
  | Builder B | 2,174 | 2,466 | |
  | Prover | | 8,687 | |
  | Gatekeeper | 28 | 7 | |
  | Lead | | | 4,891 |

  The Lead's three "Stage N starts as a plain copy of frozen stage N−1" commits add another
  42,536 lines. Those are the folder carry-forward the guide asks for, not new code.
- **One merger.** Everything reached `main` through the Gatekeeper's 61 merge commits:
  accepted handoffs, the Prover's suites, and the Lead's seeds and ledgers.

## Design choices and what they cost

| Choice | Why | Cost |
|---|---|---|
| Five seats, two builders | Parallel packages and distributed work | More tokens; merge coordination |
| A worktree per seat | Builders never trample each other's working tree | Extra worktrees must set their own Git identity (run 6 missed this once) |
| Only the Gatekeeper merges and runs the harness | One gate, no parallel heavy checks overloading the machine | The Gatekeeper becomes a queue |
| One Claude subscription for every seat | No third-party provider can stop the run | One model family; usage-limit pauses (7 h 18 m in run 6) |
| Full specification pasted into each seat's first handoff | Seats see only messages that mention them | Large first messages per stage |
| Cumulative ledger copied forward | Later stages re-check earlier requirements | The ledger grows each stage, and per-id statuses went unmaintained |
| Lead rulings bind every seat | Ended a review deadlock in an earlier run | A ruling can narrow a requirement with no counter-check (the render miss) |
| Shared memory (Cognee) | Lessons survive across runs | Optional dependency; seats continue without it |

## Failure handling

- **Missing seat:** the Lead adds that exact seat and retries the handoff; unresponsive work
  is reassigned and recorded.
- **Harness or infrastructure failure:** retried once, then reported as a blocker with the
  log.
- **Unresolvable ambiguity:** the Lead rules from the specification text and records the
  ruling.
- **Hard blocker:** recorded as the stage outcome with evidence; the band never asks the
  human.
- **A seat that stops:** the mandates say a seat never ends a turn holding unfinished work
  without telling `@lead`. Outside the room, `idle-restart.sh` restarts seats after 20 quiet
  minutes, and `billing-guard.sh` waits out usage limits and restarts the seats.

## What we would build next

Each of these rules would have caught a run 6 miss, and each is worded so it works on any
specification:

- **A ruling cannot narrow a requirement.** It settles ambiguity only. Marking a requirement
  optional or untestable needs a test showing the narrowing is safe, countersigned by the test
  writer.
- **Test the test double.** The test writer covers every option and data trait that a
  dependency's documentation or sample data describes, not only the cases with answer keys.
- **Freeze before the next specification.** The next specification is released only in the
  Gatekeeper's "frozen at `<hash>`" message.
- **Exports keep what later stages need.** Each stage's export stores everything the service
  was served.
- **A sealed acceptance suite.** The test writer runs on a second model family, keeps its suite
  outside the shared repository, and posts the suite's SHA-256 in the room before any code is
  accepted.
- **An in-run cost loop.** When a specification defines a cost, builders implement at least
  two strategies, and the Gatekeeper measures cost per correct result from the dependency's
  own log before one becomes the default.
- **A fresh workspace per run,** so a restarted seat cannot reach earlier runs' folders or live
  results.

## Standing it up

- [`SETUP.md`](SETUP.md): machine, Band Desktop settings, seats, shared memory.
- [`DISPATCH.md`](DISPATCH.md): the single message that starts a run.
- `setup/create-seats.sh claude`: creates the five seats as run 6 used them.
- `setup/prepare-result-repo.sh`: creates the result repository with one worktree per seat.
- `setup/spend.py`, `setup/economy-check.sh` and `setup/live-check.sh`: reproduce the numbers
  above.

## What we tried that failed

Runs 1 to 5 are kept as Git tags `run1/*` to `run5/*` in the result repository.

- **Claude Code seats could not start on Band Desktop 0.4.18 for Linux.** Every turn ended
  with "could not load Band's disposition MCP relay". Band passes the relay as
  `~/.local/share/jam/daemon/jam`, but the Linux package installs only `jamd` there. Claude Code
  reported the missing program as `posix_spawn 'stdio'`, which pointed at the wrong cause. We
  found it by capturing the `--settings` file Band hands Claude Code. Fix: link `/usr/bin/jam`
  to that path; `setup/create-seats.sh` now does it automatically.
- **Band refuses `--claude-disallowed-tool AskUserQuestion`,** because it is one of Band's own
  control tools. A short *Question timeout* in Settings -> Runtime covers the same risk.
- **A stage report stalled the whole band (run 2, stage 1).**
  - The Lead sent its stage report to the person, wrote "continuing with stage 2 now" and
    ended its turn.
  - Seats only see messages that mention them, and the person never answers, so no seat ever
    took another turn.
  - Fix: the Lead mandate now says a report is never the last message of a turn. The same turn
    opens the next specification and sends every seat its first handoff.
- **Review deadlocked on interpretation (also run 2, stage 1).**
  - The Gatekeeper rejected a research engine that passed every shipped check, on a literal
    reading of a requirement the Lead had already ruled on.
  - Neither seat moved, and the Lead froze the stage with passing work unmerged (110/122
    instead of 122/122).
  - Fix: rulings now bind every seat. The Gatekeeper states its dissent once with evidence, then
    reviews against the ruling.
  - Run 6 showed the price of this fix: a binding ruling can also narrow a requirement wrongly
    (see the render miss).
- **An Opus Lead and Sonnet builders were too expensive for a four-stage run.** Stage 1 alone
  cost about $73 (list price) in four hours, and a Claude Pro window ran out within about 15
  minutes of the dispatch.
- **A fallback model stopped the band for good (run 3, stage 1).**
  - When all Claude seats hit the subscription's 5-hour limit together, a guard moved them to
    Meta's Muse models through an Anthropic-compatible proxy.
  - In the real seats, Claude Code's auto permission mode could not reach the model it uses to
    approve commands, so `git` and the test runner were refused.
  - The seats ended their turns "waiting for the classifier to clear", and nothing woke them.
  - Fixes: the guard now only waits out a limit and restarts the seats. Every mandate says a
    seat never ends a turn waiting for its tools to recover; it reports an infrastructure
    blocker to the Lead in the same turn.
- **Mid-run model changes and a proxy that nudged seats (run 4, 20 November).**
  - The Codex seats (Prover, Gatekeeper) started on gpt-6.1-terra and moved to gpt-6-luna after
    stage 1. The OpenAI account ran out of quota at 08:19 UTC, and at 08:41 both moved to Meta's
    muse-spark-1.3 through `setup/model-proxy.py`. The proxy sends Meta's key, so no seat holds
    it, and translates Codex's tool format.
  - Muse seats ended turns on promises such as "sending the consolidated report now" without
    sending anything.
  - The proxy then appended a harness note ([`setup/codex-adapter-note.md`](setup/codex-adapter-note.md))
    telling the model that plain text reaches nobody. At the end of a turn with no room reply,
    it asked the model once more to do what it had said.
  - At 10:25 UTC every seat had ended its turn with work unfinished and nothing pending.
    [`setup/idle-restart.sh`](setup/idle-restart.sh) was written then.
  - At 17:07 UTC the Gatekeeper on Spark settled its last pending message with a no-reply while
    its review was unfinished, and the run stopped in stage 2.
  - Fixes in the mandates: a seat never ends a turn holding unfinished work without telling
    `@lead`, and never no-replies a handoff it has not finished. The Lead keeps an in-flight
    list. The Gatekeeper keeps a review queue and gives every handoff a verdict.
  - None of the run 4 proxy machinery was used in run 6.
- **A weak fallback model is worse than no model (run 5, stage 1).**
  - The review seats started on Kimi-K3.1-Pro and GLM-5.3 and did good work.
  - Forty minutes in, the provider's free credit ran out. We moved both seats to muse-spark-1.3
    to keep going.
  - The Gatekeeper stopped mid-review again and again, and settled the remaining handoffs
    without verdicts.
  - Fix: when a provider fails mid-run, the seats wait for a working model. A failed turn leaves
    its messages pending, and a restart on a working model resumes it.
- **A billing guard misread a Codex rate limit as a Claude usage limit** and moved the Claude
  seats to the API key needlessly. `setup/billing-guard.sh` now matches only Claude Code's own
  limit messages.
