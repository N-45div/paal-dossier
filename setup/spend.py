#!/usr/bin/env python3
"""Measure a factory run's model spend from the coding agents' own session logs.

    python3 spend.py --since 2026-11-17T10:18:00Z [--until ...]

Reads Claude Code transcripts (~/.claude/projects/**/*.jsonl, per-message usage, de-duplicated
by message id) and Codex rollouts (~/.codex/sessions/**/*.jsonl, last cumulative token count per
session). Claude is priced at list rates below; Codex prices are not built in, pass
--codex-in/--codex-cached/--codex-out (USD per million tokens) to price it. Estimates, not bills.
"""
import argparse, collections, glob, json, os
from datetime import datetime, timezone

# Anthropic list prices, USD per million tokens (platform.claude.com/docs/en/about-claude/pricing,
# read 2026-11-26): input, 5-minute cache write, 1-hour cache write, cache read, output.
# Each request is priced on its own; a rate may depend on the request's prompt length
# (input + cache reads + cache writes): Claude Haiku 5.5 bills prompts over 100,000 tokens higher.
CLAUDE = {
    "claude-fable-5-2": lambda p: (8.00, 10.00, 16.00, 0.20, 40.00),
    "claude-opus-5-5": lambda p: (4.00, 5.00, 8.00, 0.20, 20.00),
    "claude-sonnet-5-5": lambda p: (2.00, 2.50, 4.00, 0.10, 10.00),
    "claude-haiku-5-5": lambda p: (0.10, 0.125, 0.20, 0.01, 0.50) if p <= 100_000
    else (0.50, 0.625, 1.00, 0.05, 2.50),
}


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def in_window(t, a, b):
    return t is not None and (a is None or t >= a) and (b is None or t <= b)


def claude(since, until):
    seen, tot = set(), collections.defaultdict(lambda: collections.Counter())
    for f in glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True):
        for line in open(f, errors="replace"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = d.get("message") or {}
            u, mid = m.get("usage"), m.get("id")
            if not u or not in_window(ts(d.get("timestamp")), since, until) or mid in seen:
                continue
            seen.add(mid)
            i, r, w, o = (u.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens",
                                                   "cache_creation_input_tokens", "output_tokens"))
            w1 = (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0
            c = tot[m.get("model", "?")]
            c["in"] += i
            c["out"] += o
            c["cache_read"] += r
            c["cache_write"] += w
            c["messages"] += 1
            price = CLAUDE.get(m.get("model"))
            if price:
                pin, p5, p1, pr, pout = price(i + r + w)
                c["usd_micro"] += round(i * pin + (w - w1) * p5 + w1 * p1 + r * pr + o * pout)
    return tot


def codex(since, until):
    tot = collections.defaultdict(lambda: collections.Counter())
    for f in glob.glob(os.path.expanduser("~/.codex/sessions/**/*.jsonl"), recursive=True):
        last, model, start = None, "?", None
        for line in open(f, errors="replace"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = ts(d.get("timestamp"))
            start = start or t
            p = d.get("payload") or {}
            model = p.get("model", model) if isinstance(p, dict) else model
            if isinstance(p, dict) and p.get("type") == "token_count" and p.get("info"):
                if in_window(t, since, until):
                    last = p["info"]["total_token_usage"]
        if last:
            c = tot[model]
            c["in"] += last.get("input_tokens", 0) - last.get("cached_input_tokens", 0)
            c["cache_read"] += last.get("cached_input_tokens", 0)
            c["out"] += last.get("output_tokens", 0)
            c["sessions"] += 1
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since"), ap.add_argument("--until")
    ap.add_argument("--codex-in", type=float), ap.add_argument("--codex-cached", type=float)
    ap.add_argument("--codex-out", type=float)
    a = ap.parse_args()
    since, until = ts(a.since), ts(a.until)
    total = 0.0
    print(f"{'model':22} {'input':>12} {'cache read':>14} {'cache write':>12} {'output':>11} {'USD':>9}")
    for model, c in sorted(claude(since, until).items()):
        p = CLAUDE.get(model)
        usd = c["usd_micro"] / 1e6
        total += usd
        print(f"{model:22} {c['in']:>12,} {c['cache_read']:>14,} {c['cache_write']:>12,} {c['out']:>11,} {usd:>9.2f}{'' if p else ' (unpriced)'}")
    for model, c in sorted(codex(since, until).items()):
        usd = None
        if a.codex_in is not None and a.codex_out is not None:
            usd = (c["in"] * a.codex_in + c["cache_read"] * (a.codex_cached or 0) + c["out"] * a.codex_out) / 1e6
            total += usd
        print(f"{'codex:' + model:22} {c['in']:>12,} {c['cache_read']:>14,} {'-':>12} {c['out']:>11,} "
              f"{(f'{usd:9.2f}' if usd is not None else '  unpriced')}")
    print(f"{'total (priced)':22} {'':>12} {'':>14} {'':>12} {'':>11} {total:>9.2f}")


if __name__ == "__main__":
    main()
