# Dispatch prompts

Paste one of these into a fresh room that already holds all five seats. It is the only
message you send until the Lead's final report. Replace `<you>` with your Linux user name
and `@<your-handle>` with your own Band handle.

## Judged run (Dossier, all four stages)

```text
@lead You are the lead seat for this factory run. Build all four stages of the track below,
coordinating @builder-a, @builder-b, @prover and @gatekeeper as your mandate describes. This
message is the only human input for the run: do not ask me anything and do not wait for me.
Report each stage's outcome to @<your-handle> when it is frozen, then continue.

Track: dossier
Workspace root: /home/<you>/buildathon
Kickoff checkout (read-only): /home/<you>/buildathon/sf-buildathon-2026
Result repository, integration checkout on branch main, merged only by @gatekeeper:
  /home/<you>/buildathon/band-work/result
Worktrees, one branch each in the same repository:
  @lead       /home/<you>/buildathon/band-work/result-wt/lead
  @builder-a  /home/<you>/buildathon/band-work/result-wt/builder-a
  @builder-b  /home/<you>/buildathon/band-work/result-wt/builder-b
  @prover     /home/<you>/buildathon/band-work/result-wt/prover
Check reports: /home/<you>/buildathon/band-work/checks (a new subfolder for every run)
Shared lock for container builds and check runs: prefix the command with
  flock /tmp/factory-heavy.lock

Specifications. Open each one only when its stage begins, in this order:
  1. /home/<you>/buildathon/sf-buildathon-2026/challenges/dossier/spec/stage-1.md  -> stage-1/
  2. /home/<you>/buildathon/sf-buildathon-2026/challenges/dossier/spec/stage-2.md  -> stage-2/
  3. /home/<you>/buildathon/sf-buildathon-2026/challenges/dossier/spec/stage-3.md  -> stage-3/
  4. /home/<you>/buildathon/sf-buildathon-2026/challenges/dossier/spec/stage-4.md  -> stage-4/
Stage 1 starts from an empty folder. Each later stage starts as a plain copy of the frozen
folder before it and extends that copy. Every stage folder is a complete, buildable service
with its own Dockerfile, RUN.md and source. Never change a folder once the next
specification has been opened.

Mock provider web for local testing:
  /home/<you>/buildathon/sf-buildathon-2026/challenges/dossier/web/README.md

Event check, run only by @gatekeeper, one at a time, from the kickoff checkout:
  cd /home/<you>/buildathon/sf-buildathon-2026 && . .venv/bin/activate
  flock /tmp/factory-heavy.lock python -m harness run --track dossier \
    --repo /home/<you>/buildathon/band-work/result --stage N \
    --out /home/<you>/buildathon/band-work/checks/sN-<run-number>
  Each stage's final check adds --mode isolated and uses --out .../checks/sN-final.
The shipped checks are a partial sample. Implement the specification, not the checks.
Each run also probes the next stage's suite to confirm the folder does not overshoot; that
line is expected to fail. Never open, read or relay the next stage's check files or logs,
and open files under challenges/dossier/test/ only for stages that have started.

Save wall-clock time: run independent work in parallel and do not repeat verification
another seat has already done.
```

## Rehearsal (toy track)

Same message with these changes: `Track: toy`; result repository
`/home/<you>/buildathon/band-work/toy-result` and its `toy-result-wt/` worktrees; specs at
`.../challenges/toy/spec/stage-N.md`; harness `--track toy --repo .../toy-result`; drop the
mock web line. Practice rooms may be steered; the judged room may not.
