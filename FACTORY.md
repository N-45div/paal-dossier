# Factory

This repository was built by a five-seat "dark factory" band running in a Band room. A
single human dispatch message started the run; after it no seat asked a human anything.

## Seats

| Seat | Mandate | Role |
|---|---|---|
| Lead | `mandates/lead.md` | Reads each stage's specification, writes the cumulative requirements ledger (`stage-N/LEDGER.md`), records rulings on ambiguities, splits work into packages with disjoint code areas, tracks verdicts, freezes stages |
| Builder A | `mandates/builder-a.md` | Implements its packages in its own git worktree and hands off exact commits |
| Builder B | `mandates/builder-b.md` | Same, for a disjoint area of the code |
| Prover | `mandates/prover.md` | Writes an independent black-box acceptance suite (`acceptance/stage-N/`) from the specification text alone, never from product code |
| Gatekeeper | `mandates/gatekeeper.md` | The only seat that merges: rebuilds each handed-off commit in a fresh checkout, runs the acceptance suite and the event check, plants defects to test the tests, merges accepted work, runs each stage's final isolated check |

## Flow per stage

1. The lead opens only the current stage's specification, quotes every normative statement
   into the ledger with an id (`R<stage>.<n>`), an owning package and a status
   (`open` → `built` → `tested` → `accepted`), and adds rulings (`L<stage>.<n>`) with reasons.
2. Every seat receives the full specification text plus its assignment; both builders start
   at once on disjoint areas, and the first package always produces a service that builds
   and starts so the Prover and Gatekeeper can work against it early.
3. Builders hand off commits with the verbatim requirement text they claim. The Gatekeeper
   reviews each one in a throwaway checkout, combines candidates when packages depend on
   each other, and merges to `main` only after the build, the acceptance suite, the event
   check and its defect-planting pass.
4. Rejections go back to the owning builder with the quoted requirement and evidence; the
   lead logs every rejection and what it changed in the ledger's verdict log.
5. A stage freezes only on the Gatekeeper's final isolated check. The frozen folder is
   copied as plain files to the next stage's folder, which then extends it; a frozen
   folder never changes again.

## Measures

Every cost, latency and resource limit in a specification is a ledger requirement with a
measure (for example units spent per build from the provider mock's call log, build time,
start-to-healthy time, request latency under 50 concurrent requests) that is reported on
each candidate against the previous accepted revision.

## Shared resources

Each seat uses its own port range and name prefix; container builds and check runs are
serialised with `flock /tmp/factory-heavy.lock`. During the run all research goes to the
local mock web; no live provider key is used.
