# The Ledger Factory

> DRAFT. Sections marked TBD are filled from rehearsal and judged-run measurements.

A five-seat software factory for Band Desktop. It turns a written specification into a
numbered **requirements ledger**, builds against it in parallel, proves each requirement
with tests written independently of the code, and lets only verified work reach the
integration branch. Nothing in the mandates names a problem domain: point the factory at a
different specification and it runs the same way.

## Seats

| Seat | Harness | Model | Owns |
|---|---|---|---|
| Lead | Claude Code | claude-sonnet-5-5 (high) | Ledger, work packages, rulings, stage freeze, reports |
| Builder A | Claude Code | claude-haiku-5-5 (medium) | Implements assigned packages |
| Builder B | Claude Code | claude-haiku-5-5 (medium) | Implements assigned packages |
| Prover | Claude Code | claude-haiku-5-5 (medium) | Black-box acceptance tests derived from the specification |
| Gatekeeper | Claude Code | claude-sonnet-5-5 (medium) | Clean-room review, all check runs, merges, final checks |

Mandates: [`mandates/`](mandates/). Each one says how a seat works, never what it builds.

The submitted band runs every seat on one Claude subscription: Sonnet where judgement gates
the work (the Lead and the Gatekeeper), Haiku where the work is well specified (builders and
Prover). Earlier runs put the Prover and Gatekeeper on other model families through Codex and
[`setup/model-proxy.py`](setup/model-proxy.py), which picks each seat's model and translates
Codex's tool format. That kept test writer and reviewer independent of the builders, but
every third-party provider failed mid-run (quota, credit, or a model that could not hold a
long review), and each failure stopped the band. The independence now comes from the
mandates instead: the Prover derives tests from the specification and never reads product
code first, and the Gatekeeper reviews on a stronger model than the builders. Before run 5,
each candidate review model was given a coding task and a review of a commit with a planted
bug that the builder's own test missed. One candidate claimed a commit it had not made and
was dropped.

**Mid-run model changes (judged run).** The Codex seats ran stage 1 on gpt-6.1-terra. Stage 1
alone used about 530M input tokens, so after the freeze both were moved to gpt-6-luna. At
08:19Z on Nov 20, early in stage 2, the OpenAI account ran out of quota. At 08:41Z both seats
moved to Meta's muse-spark-1.3, which serves the OpenAI Responses API. At 08:49Z the Gatekeeper
moved to muse-wonder-1.0, which was about 3x faster in a probe. The Gatekeeper is the queue
every review and check waits on, and the move also keeps test writer and reviewer on
different models. The proxy finds the calling seat from the socket's owning process.
Wonder did not hold up in the seat. On its second turn one response streamed for 18 minutes
and ended with "Incomplete response, reason: max_output_tokens", which ended the turn, so at
09:19Z the Gatekeeper went back to muse-spark-1.3 and was restarted to resume its pending
handoff.
On its first turn on Muse, the Gatekeeper merged an update, wrote "sending the consolidated
report now", marked its 17 queued messages as needing no reply, and ended the turn without
sending anything. From 08:55Z the proxy appends a short harness note,
[`setup/codex-adapter-note.md`](setup/codex-adapter-note.md), to the Muse seats'
instructions. It says nothing about the task. It tells the model that plain assistant text
reaches nobody and that it must make the reply call before ending a turn, which GPT models
running in Codex already know.
The note did not fully stop this. At 09:34Z the Prover ended its turn on "verifying the
controls and completing the re-handoff" without sending the handoff, and was restarted at
10:02Z. From 10:15Z the proxy also checks the end of each turn. When a Muse turn ends with no
tool call and its last message reads as an intention (for example "now ..." or "— sending
..."), the proxy asks the model once more, in the same response stream, to do what it said
or to answer "done". This happens at most once per conversation every ten minutes, so it
cannot loop. Wording alone missed endings such as "Continuing the engine-scoped P5
verification.", which stopped the Gatekeeper mid-review several times in stage 2, so from
16:39Z the check also runs whenever a turn ends without a room reply or no-reply call, since
every Band turn ends with one of them.

**The band went idle with no message left to answer (judged run, stage 2).** At 10:25Z every
seat had ended its turn:
- Builder B had answered the Lead's rulings but not handed off its package.
- Builder A was waiting for Builder B's module to reach main.
- The Lead believed both builders were still working.
- The Gatekeeper had set aside the review it had announced.

Seats act only when a message mentions them, so nothing would ever move. A restart makes each
seat resume its own open tasks, and Builder B went straight back to work. Restarting sends
nothing into the room, so it is not steering. [`setup/idle-restart.sh`](setup/idle-restart.sh)
now restarts all seats when the room has been idle for 20 minutes, at most once every 30
minutes. The mandate-level fix is now in the mandates (see "What we tried that failed"): a
seat never ends a turn with its work unfinished and unreported, and the Lead treats a quiet
seat as idle. None of this was posted
in the room, and no seat was recreated. Band fixes a seat's model at creation, so Codex reaches
the model through a local `model_provider` in `~/.codex/config.toml` pointing at
[`setup/model-proxy.py`](setup/model-proxy.py). The proxy rewrites the model id, and for Meta
also does two more things:
- it sends Meta's key, so the key never reaches the seat;
- it translates Codex's tool format (namespaced tools and the freeform `exec` tool, which
  Meta does not accept) into plain function tools and back.

Before the seats moved, the translation was tested on a scratch task: write code, write a
pytest suite, run it and commit. [`setup/switch-codex-model.sh`](setup/switch-codex-model.sh)
restarts each seat only after it has been quiet for three minutes, then checks the proxy log.
If no seat request reaches the new model within 20 minutes, it reverts.

## One stage, end to end

```text
dispatch -> @lead reads the stage spec, writes the ledger (every "must" = one id, quoted verbatim)
         -> @builder-a + @builder-b build disjoint packages      } in parallel
         -> @prover writes tests per ledger id from the spec only }
         -> builder hands off commit -> @gatekeeper: clean clone, build, run, test, read diff
              REJECT (failing ids + evidence) -> builder fixes -> hands off again
              ACCEPT -> merge into main
         -> all packages in -> @gatekeeper final check (isolated) -> @lead freezes the folder,
            copies it forward, and only then opens the next specification
```

## How it catches bad work

1. **The ledger.** Every normative sentence, table row and appendix rule becomes an id with
   the specification quoted. A stage is accepted only when every id has code, a test and a
   pass. This is aimed at requirements a happy-path check never exercises.
2. **Independent tests.** The Prover derives expected behaviour from the specification,
   never from the implementation, and never copies the event's shipped checks. Tests and code
   are written by different seats on different model families.
3. **Clean-room review.** The Gatekeeper builds every handed-off commit from a fresh
   checkout, following the run instructions literally, so uncommitted files, broken run
   instructions and nested repositories fail before they reach main.
4. **Diff review.** The Gatekeeper rejects logic that branches on a check's inputs, weakened
   tests, changes to frozen folders, and credentials.
5. **Isolated final check.** Each stage ends with the event check in isolated mode, which
   catches dependencies on outbound network access.
6. **Loop guard.** An id rejected three times is re-planned by the Lead (split, reassigned or
   re-derived) instead of retried.

## Design choices and what they cost

| Choice | Why | Cost |
|---|---|---|
| Five seats, two builders | Parallel packages and clearly distributed work | More tokens; merge coordination |
| Separate worktree and git identity per seat | Builders never trample each other's working tree; history shows who wrote what | One-time setup script |
| Only the Gatekeeper merges and runs the harness | One gate, no parallel heavy checks overloading the machine | Gatekeeper can become a queue |
| One Claude subscription for every seat | No third-party provider can stop the run mid-stage | Shared usage limits; the guard waits out a limit and restarts the seats |
| Full specification pasted into each seat's first handoff | Seats see only messages that mention them; pointers lose context | Large first messages per stage |
| Cumulative ledger copied forward | Later stages re-verify earlier requirements | Ledger grows each stage |
| Shared memory (Cognee) for rulings and rejection lessons | Context survives compaction and stage boundaries | Optional dependency; seats continue without it |

## Failure handling

- Missing seat: the Lead adds that exact seat and retries the handoff; unresponsive work is
  reassigned and recorded.
- Harness or infrastructure failure: retried once, then reported as a blocker with the log.
- Unresolvable ambiguity: the Lead rules from the specification text and records the ruling.
- Hard blocker: recorded as the stage outcome with evidence; the band never asks the human.

## Memory and live research

**Shared memory (Cognee Cloud).** Every seat reaches one Cognee Cloud tenant over MCP
(`setup/cognee.sh cloud`), dataset `paal-org-brain`. Before a run, that dataset holds the
retrospectives of earlier runs. During a run,
[`setup/memory-scribe.py`](setup/memory-scribe.py) copies every verdict, ruling, freeze and
blocker from the room into the same dataset every 20 minutes, verbatim, so the record does
not depend on a seat remembering to store it. The scribe only reads the room and writes
memory; it never posts and adds nothing a seat did not say. It matches the decision words the
mandates use, never anything about the problem.

What run 6 actually did with it:

- **Seats:** two calls, both by the Lead. At its first step it recalled the lessons of runs
  1 to 5 (the review rules that earlier runs learned the hard way). When stage 1 froze, it
  stored that stage's retrospective. No other seat called memory, and the Lead did not
  recall again in stages 2 to 4: the ledger, the git history and the room gave it what it
  needed.
- **Scribe:** 17 batches, 136 decisions stored, from the first verdict to the final report.
- **After the run:** the dataset answers questions about the run. Asked which stage 4
  handoffs were rejected and why, it returned both commits and the traceability gap that
  caused each rejection. The next run's Lead starts from that record.

The lesson: memory earns its place across runs, not within one. Inside a run the room and
the ledger are faster and exact. A mandate that told every seat to recall before each
package would cost turns and add little.

**Live research (Nimble).** Seats never hold a live provider key: everything a seat runs is in
the published room log, and checks run against the mock web. After each stage freezes,
[`setup/live-check.sh`](setup/live-check.sh) builds the frozen folder from the integration
branch and researches real companies through Nimble, following the event guide's steps.
Results stay outside the result repository, so the band never sees them; after the last
stage, the `runway.com` result of the highest completed stage is committed as
`dossier-runway.com.json`.

## Standing it up

See [`SETUP.md`](SETUP.md) (machine, Band Desktop settings, seats, shared memory) and
[`DISPATCH.md`](DISPATCH.md) (the single message that starts a run).
`setup/prepare-result-repo.sh` creates the result repository with one worktree per seat.

## Measured cost and time

Judged run 6, 2026-11-21, one dispatch at 05:07:23 UTC, all five seats on one Claude Pro
subscription. Times come from the room's timestamps; the verdict counts are room messages
that carry the Gatekeeper's word, so a message that rules on two handoffs counts once.

| Stage | Frozen (UTC) | Wall clock | Paused on the Pro limit | Working time | Messages carrying ACCEPT / REJECT |
|---|---|---|---|---|---|
| 1 | 05:44 | 0 h 37 m | none | 0 h 37 m | 9 / 5 |
| 2 | 07:33 | 1 h 49 m | 06:00 to 06:18 | 1 h 31 m | 21 / 1 |
| 3 | 12:43 | 5 h 10 m | 07:46 to 11:18 | 1 h 38 m | 10 / 3 |
| 4 | 17:30 | 4 h 47 m | 12:55 to 16:23 | 1 h 19 m | 5 / 3 |
| Total | | 12 h 23 m | 7 h 18 m | 5 h 05 m | 45 / 12 |

- **Result.** The event's harness in isolated mode passes stages 1, 2, 3 and 4 on the frozen
  revision. At the last freeze the band's own checks stood at 271 acceptance tests passed,
  0 failed; 519 unit and service tests; 2 UI tests; and 18 of 18 restart scenarios. The
  Gatekeeper planted three defects in stage 4, and the tests caught all three.
- **Where the time went.** More than half the wall clock was waiting for the Pro 5-hour
  window to reset; `billing-guard.sh` slept through each limit and restarted every seat,
  which resumed its pending work with nothing lost. A larger subscription would cut the
  pauses without changing anything else.
- **Model spend.** Flat: the Pro subscription, no per-token billing. The room log holds 9,589
  messages, including 3,297 tool calls, 391 text messages and 13 error messages (all of them
  Pro-limit notices).
- **What rejections changed.** In stage 4 two handoffs were rejected, both for traceability:
  they cited ledger rows that no test named. The builders added the missing tests, and the
  work was accepted on resubmission. In the same stage, a budget test failed only when it ran
  after the Prover's new restart module. The Lead ruled it a test defect, and the Prover fixed
  the module's teardown.
- **Live research.** The Nimble checks after each freeze are kept in `band-work/live/`
  outside the repository, along with each service log; see `dossier-runway.com.json` in the
  result repository for the final one.

## What we tried that failed

- **Claude Code seats could not start on Band Desktop 0.4.18 for Linux.** Every turn ended
  with "could not load Band's disposition MCP relay". Band passes the relay as
  `~/.local/share/jam/daemon/jam`, but the Linux package installs only `jamd` there; Claude
  Code reported the missing program as `posix_spawn 'stdio'`, which pointed at the wrong
  cause. Found by capturing the `--settings` file Band hands Claude Code. Fix: link
  `/usr/bin/jam` to that path; `setup/create-seats.sh` now does it automatically.
- Band refuses `--claude-disallowed-tool AskUserQuestion`: it is one of Band's own control
  tools. A short *Question timeout* in Settings -> Runtime covers the same risk.
- **A stage report stalled the whole band (practice run, stage 1).** The Lead sent its stage
  report to the person, wrote "continuing with stage 2 now" and ended its turn. Seats only see
  messages that mention them, and the person never answers, so no seat ever took another
  turn. Fix: the Lead mandate now says a report is never the last message of a turn; the same
  turn opens the next specification and sends every seat its first handoff.
- **Review deadlocked on interpretation (same run).** The Gatekeeper rejected a research
  engine that passed every shipped check, on a literal reading of one requirement the Lead had
  already ruled on. Neither seat moved, and the Lead froze the stage with passing work unmerged
  (110/122 instead of 122/122). Fix: rulings now bind every seat. The Gatekeeper states its
  dissent once with evidence, then reviews against the ruling, and the Lead must settle a
  reading dispute in its next turn.
- **Opus Lead + Sonnet builders were too expensive for a four-stage run.** Stage 1 alone
  cost about $73 (list price, Claude seats) in four hours, and a Claude Pro window ran out
  within about 15 minutes of the dispatch. The submitted factory runs a Sonnet Lead and Haiku
  builders, keeping the review seats on a different model family.
- **A fallback model stopped the band for good (practice run 3, stage 1).** When all three
  Claude seats hit the subscription's 5-hour limit together, a guard moved them to Meta's Muse
  models through an Anthropic-compatible proxy. A small coding test had passed, but in the real
  seats Claude Code's auto permission mode could not reach the model it uses to approve commands,
  so `git` and the test runner were refused, and Muse rejected some long-session requests. The
  seats ended their turns "waiting for the classifier to clear", no seat held a mention, and
  nothing ever woke them. Fixes: the guard now only waits out a limit and restarts the seats
  (seats that failed mid-turn on a limit pick their work back up, as run 2 showed), and every
  mandate says a seat never ends a turn waiting for its tools to recover: it reports an
  infrastructure blocker to the Lead in the same turn.
- **The review seat on a weaker model stopped the band for good (run 4, stage 2).** After
  the OpenAI quota ran out, the Gatekeeper ran on muse-spark-1.3. It lost track of long
  reviews: it re-reviewed a package it had already merged, narrated the same status line
  dozens of times without acting, and at 17:07Z on Nov 20 settled its last pending message
  with a no-reply while its review was unfinished. With no message pending for any seat,
  restarts had nothing to resume, and the rules forbid posting in the room, so the run
  stopped with stage 2 partly merged. Proxy-side end checks (above) reduced early stops but
  could not fix this. Fixes in the mandates: a seat never ends a turn holding unfinished work
  without telling `@lead` its status and next step, and never no-replies a handoff it has not
  finished; the Lead keeps an in-flight list and treats a seat that stopped without reporting
  as idle; the Gatekeeper keeps a review queue, skips commits already merged and gives every
  handoff a verdict. The review seat needs a model that holds long tasks.
- **A weak fallback model is worse than no model (run 5, stage 1).** The review seats started
  on Kimi-K3.1-Pro and GLM-5.3 and did good work: the first reject, ruling and fix took two
  minutes. Forty minutes in, the provider's free credit ran out and every call failed. A
  failed turn leaves its messages pending, so a restart on a working model resumes it. We
  instead moved both seats to muse-spark-1.3 to keep going. The Gatekeeper on Spark stopped
  mid-review again and again, merged one package after five hours, and settled the remaining
  handoffs without verdicts, so at 01:15Z on Nov 21 no seat had anything left to answer. Its
  last message, that a commit was already merged, went only to the builder, and the builder
  did not tell the Lead. Fixes: when a provider fails mid-run, the seats wait for a working
  model instead of falling back to a weak one; the Gatekeeper reports "already merged" to
  `@lead` too; and a builder whose package is merged tells `@lead` its next step in the same
  turn.
- **A billing guard misread a Codex rate limit as a Claude usage limit** and moved the Claude
  seats from the subscription to the API key needlessly. `setup/billing-guard.sh` now matches
  only Claude Code's own limit messages.
