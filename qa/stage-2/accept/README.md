# Stage 2 independent acceptance suite

The suite tests only HTTP, browser behavior and the mock provider's own log. It
does not import the submitted service. `CLAIMS.md` indexes named Stage 2 ledger
requirements; a reference identifies exercised behavior, not complete proof of
every subclause. Visual quality and the generated screenshots require review.
The optional browser-vendor calls are checked if used; their use is not required.
In particular, optional WebRouter configuration (R2.20–R2.21) and the four-session
provider cap (R2.29) have no direct exercise when the service uses Nimble render
alone. R2.107 does not prohibit background synchronization, so the suite does not
assert its absence.

From the prover worktree, run with the seat's Docker prefix and host port range:

```sh
python3 qa/stage-2/accept/run.py --service-root <stage2-worktree> \
  --stage1-root <frozen-stage1-worktree> --name-prefix gatekeeper \
  --port-start 18300 --port-end 18399 -q --tb=line
```

The runner takes `/tmp/factory-heavy.lock`, creates an ephemeral venv from a
Docker-built wheelhouse, and removes only its own named resources. The real
Chromium browser runs in a mock-web image container on an internal Docker network;
tests drive its DevTools interface without reaching the public internet. Browser
screenshots are written as `/tmp/<name-prefix>-stage2-*.png`. The controlled corpus is
generated in temporary directories. It includes a page whose static and rendered
text differ and a research-cited page whose cited claim is unsupported.

The frozen Stage 1 is exercised separately during the upgrade test. If
`--stage1-root` is omitted, the runner expects `stage-1/` and `stage-2/` under the
same service root. The Stage 1 API and framing regression files in this suite are
copies of our own previously reviewed acceptance tests, run against Stage 2; their
Stage 1 requirement index is `../../stage-1/accept/CLAIMS.md`. Stage 2 explicitly
excludes 429 retry waits from the build deadline; the copied fault regression is
adapted to that rule, while `test_rate_limits.py` measures retry spacing and the
remaining active-time bound from an independent provider proxy.

The upgrade bridge deliberately serves Stage 2 HTML while routing API calls to the
frozen Stage 1 until the test switches it. This makes a lost, committed Stage 1
write retryable in the same browser after import, without inspecting service code.
