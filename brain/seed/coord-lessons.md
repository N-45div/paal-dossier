# Lessons from Coord, a four-seat Band factory (Tablekeeper track, Oct 2026)

Source: https://github.com/N-45div/Coord/blob/main/FACTORY.md. Process lessons only: how the factory planned, verified, failed and recovered. All four stages were delivered in 5 h 19 m for about $145 at list prices.

## Design choices, and what they cost

1. **A requirements ledger before any code.** Coordinator turns each spec into numbered
   obligations (105, 42, 51 and 30 for stages 1 to 4) with the section they come from and
   how each is observed, and records every reading of ambiguous text as a decision
   (A-01 to A-47). Tests, rejections and Gate's coverage audit all point at ledger numbers.
   *Why:* the shipped checks are a fraction of the graded ones; the ledger is how the band
   looks for what they never ask. *Cost:* about 6 minutes before stage 1's first handoff.
2. **Builder and Verifier start together, from the same ledger.** Verifier never opens
   product source and derives every expected value from the spec. *Why:* a test written
   after reading the code tests the code. *Cost:* duplicated spec reading, and a suite that
   sometimes misreads the spec: it did, 4 times in stage 2 and 3 in stage 4, each declared
   and fixed in the room. Independence is procedural (the repository is shared), and the
   mandate says so.
3. **Gate is the only acceptance, and it reproduces everything.** Clean no-cache build of
   the exact commit, the organisers' harness in graded isolated mode, the Verifier's suite
   re-run by Gate, its own probes (stage 1: 240, stage 2: 55 plus 83 Playwright UI checks,
   stage 3: 175, stage 4: 91), upgrades from the real earlier images, a line-by-line ledger
   audit and a read of the code that enforces invariants. *Cost:* Gate is the most
   expensive seat (about 38% of the run's estimated spend).
4. **Gate tests the tests.** After a passing baseline, Gate plants one bug per throwaway
   copy and runs the frozen suite. Results: stage 1 8/9 caught, stage 2 8/8, stage 3 7/8,
   stage 4 9/10. Every survivor went back to Verifier as a missing test, reported as
   tuned, never as first-time detection.
5. **Generic mandates; specifics live in one message.** The mandates name no endpoint,
   field or error code (`harness check` and our own scan against both tracks' vocabulary
   are clean). The track, paths, check commands, constraints and hard stop are all in
   [`dispatch.md`](dispatch.md). The same four files ran an unscored rehearsal on a
   different problem before this run.
6. **Every seat commits under its own name**, staging only its own paths: Verifier 20
   commits, Builder 11, Coordinator 12, Gate 9. `git log --format='%an %s'` is the
   division of labour.

## Failures and recoveries during the run

- **E-01, 21:59–23:14: the Docker daemon hung.** Gate reported a BLOCKER ("environment,
  not product"); Coordinator froze Docker work, set rules (seat-prefixed container names,
  timeouts on every docker call, one harness run per seat) and polled read-only. Its own
  attempt to restart Docker was refused by its runtime permissions. The operator (a human,
  outside the room) found the cause, the host disk full, and restarted Docker; no message
  was sent to the room. Coordinator detected the recovery and posted DOCKER READY at 23:14.
  The disk was being filled by the host's antivirus web-protection tracing, which wrote a
  133 MB log every few minutes while the seats worked (16 GB in total).
- **E-02:** a port collision voided one Gate run, so each seat got its own port range.
- **E-03, about 01:52–01:58: Docker Desktop and the WSL VMs stopped.** The operator started
  Docker Desktop again; every interrupted run was voided and repeated, and Coordinator
  added a load rule (at most 5 containers per seat, one harness run on the machine at a
  time). E-04 turned out to be a misattribution of the same event.
- Every interrupted check was rerun on the exact commit; no acceptance relied on a run that
  overlapped an outage.

## What we tried that failed

- Bare-context seats (to keep the operator's personal Claude Code instructions out of them)
  cannot use a Claude subscription. Seats run in `local_config` mode instead, and the
  operator's global CLAUDE.md is excluded with `claudeMdExcludes` in the seats' working
  directory ([`factory/claude-settings.local.json`](factory/claude-settings.local.json)).
- Band Desktop launches the `claude` found on PATH; an old global install failed the first
  rehearsal turn with a model-version error. Update Claude Code before creating seats.
- Creating seats with every permission check disabled was refused by the operator's own
  agent's safety check; we kept Band's default Auto mode and set Band's "Human approval
  wait" to auto-deny after 5 minutes, so nothing can stall on a human overnight.
- In rehearsal, seats took up to 18 minutes to acknowledge a handoff because a busy seat
  only reads new messages when its turn ends. Coordinator's handoffs ask for an
  acknowledgement but tell receivers to proceed without waiting for a reply, and Builder
  and Verifier never wait for each other, which kept the real run moving.

