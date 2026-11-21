# Lessons from Paal setup and rehearsal (Nov 2026)


- **Claude Code seats could not start on Band Desktop 0.4.18 for Linux.** Every turn ended
  with "could not load Band's disposition MCP relay". Band passes the relay as
  `~/.local/share/jam/daemon/jam`, but the Linux package installs only `jamd` there; Claude
  Code reported the missing program as `posix_spawn 'stdio'`, which pointed at the wrong
  cause. Found by capturing the `--settings` file Band hands Claude Code. Fix: link
  `/usr/bin/jam` to that path; `setup/create-seats.sh` now does it automatically.
- Band refuses `--claude-disallowed-tool AskUserQuestion`: it is one of Band's own control
  tools. A short *Question timeout* in Settings -> Runtime covers the same risk.
- Further entries TBD from rehearsals.
- Run every tool inside WSL2 Ubuntu (Band Desktop's .deb, Docker Engine, Claude Code, Codex);
  keep the WSL disk on a large drive. Band Desktop launches programs without your shell
  profile, so put `claude` and `codex` launchers in /usr/local/bin.
- Give each seat its own git worktree, branch and identity; only the Gatekeeper merges.
- Rehearse on the cheapest models first: the rehearsal tests plumbing, not quality.
- A Lead's stage report to the person must never end its turn: in the same turn, send every
  seat its next handoff, or the band idles forever (seats see only messages that mention them).
- Interpretation belongs to the Lead. If the Gatekeeper rejects on a reading the Lead has ruled
  on, the ruling binds; never freeze a stage with passing work held back by a reading dispute.
- Price the Lead's model first: an Opus Lead with high effort was the single largest cost of a
  stage. A Sonnet Lead with Haiku builders costs about a third.
