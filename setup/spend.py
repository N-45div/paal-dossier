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

# USD per million tokens: input, output, cache read, cache write (5-minute, 1.25x input)
CLAUDE = {
    "claude-fable-5-2": (8.00, 40.00, 0.20, 10.00),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
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
            c = tot[m.get("model", "?")]
            c["in"] += u.get("input_tokens", 0)
            c["out"] += u.get("output_tokens", 0)
            c["cache_read"] += u.get("cache_read_input_tokens", 0)
            c["cache_write"] += u.get("cache_creation_input_tokens", 0)
            c["messages"] += 1
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
        usd = (c["in"] * p[0] + c["out"] * p[1] + c["cache_read"] * p[2] + c["cache_write"] * p[3]) / 1e6 if p else 0.0
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
