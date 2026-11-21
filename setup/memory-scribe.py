#!/usr/bin/env python3
"""Copy a room's decisions into shared memory as they happen.

    python3 memory-scribe.py <room-id> [--dataset paal-org-brain] [--every 20]

Every few minutes it reads the room's new text messages, keeps the ones that record a
decision (verdicts, rulings, freezes, blockers), and stores them in Cognee over MCP as one
document per batch. Seats recall it at the start of each stage, so what one stage learned
is there for the next even when no seat stored it itself.

It only reads the room and writes memory: it never posts, and it adds nothing a seat did not
already say in the room. It matches the words the mandates use for decisions, never anything
about the problem being built. MCP endpoint: COGNEE_MCP_URL (default the cognee-cloud bridge).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

MCP = os.environ.get("COGNEE_MCP_URL", "http://localhost:8766/mcp")
DECISION = re.compile(r"\b(ACCEPT|REJECT|FINAL ACCEPT|FINAL REJECT|RULING|ruling|ruled|"
                      r"frozen|freeze|blocker|re-plan|replan|dissent)\b")
STATE = os.path.expanduser("~/.memory-scribe-state.json")


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def band(*args):
    out = subprocess.run(["band", *args], capture_output=True, text=True, timeout=120)
    return out.stdout


def participants(room):
    """Handles by participant id, and the display names of the people (not seats) in the room."""
    names, people = {}, set()
    for line in band("room", "participants", room).splitlines():
        m = re.match(r"(\S+) \[\w+\] (.*) \((User|Agent); id=([0-9a-f-]{36})\)", line)
        if m:
            names[m.group(4)] = "@" + m.group(1).split("/")[-1]
            if m.group(3) == "User":
                people.add(m.group(2).strip())
    return names, people


def new_messages(room, since):
    """Text messages newer than `since`, oldest first (pages back until older)."""
    found, cursor = [], None
    for _ in range(50):
        args = ["room", "messages", room, "--json", "--type", "text"]
        if cursor:
            args += ["--cursor", cursor]
        page = json.loads(band(*args) or "{}")
        msgs = page.get("messages") or []
        found += [m for m in msgs if m.get("inserted_at", "") > since]
        cursor = page.get("next_cursor")
        if not cursor or not msgs or min(m.get("inserted_at", "") for m in msgs) <= since:
            break
    return sorted(found, key=lambda m: m.get("inserted_at", ""))


def mcp_call(tool, args):
    headers = {"content-type": "application/json", "accept": "application/json, text/event-stream"}

    def post(msg, sid=None):
        h = dict(headers, **({"mcp-session-id": sid} if sid else {}))
        req = urllib.request.Request(MCP, data=json.dumps(msg).encode(), headers=h)
        with urllib.request.urlopen(req, timeout=600) as r:
            body, sid = r.read().decode(), r.headers.get("mcp-session-id") or sid
        data = [json.loads(l[5:]) for l in body.splitlines() if l.startswith("data:")]
        return (data[-1] if data else (json.loads(body) if body.strip().startswith("{") else None)), sid

    _, sid = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "memory-scribe", "version": "1"}}})
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    res, _ = post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                   "params": {"name": tool, "arguments": args}}, sid)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("room")
    ap.add_argument("--dataset", default="paal-org-brain")
    ap.add_argument("--every", type=int, default=20, help="minutes between batches")
    a = ap.parse_args()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    since = state.get(a.room, "")
    while True:
        try:
            names, people = participants(a.room)
            msgs = new_messages(a.room, since)
            keep = []
            for m in msgs:
                text = str(m.get("content", ""))
                # the person's dispatch and pasted specifications are not decisions
                if (m.get("sender_name") or "").strip() in people or len(text) > 6000:
                    continue
                if DECISION.search(text):
                    text = re.sub(r"@\[\[([0-9a-f-]{36})\]\]", lambda x: names.get(x.group(1), "@seat"), text)
                    who = m.get("sender_name") or "seat"
                    keep.append(f"### {m['inserted_at'][:19]}Z {who}\n{text[:2000]}")
            if msgs:
                since = msgs[-1]["inserted_at"]
            if keep:
                doc = (f"# Band decisions, room {a.room[:8]}, {keep[0][4:24]} to {keep[-1][4:24]}\n\n"
                       "Verdicts, rulings, freezes and blockers, copied verbatim from the room.\n\n"
                       + "\n\n".join(keep))
                res = mcp_call("remember", {"data": doc, "dataset_name": a.dataset})
                ok = res and not res.get("result", {}).get("isError")
                log(f"stored {len(keep)} decisions ({len(msgs)} new messages): {'ok' if ok else res}")
            else:
                log(f"{len(msgs)} new messages, no decisions")
            state[a.room] = since
            json.dump(state, open(STATE, "w"))
        except Exception as err:  # keep running through network or service errors
            log(f"error: {err}")
        time.sleep(a.every * 60)


if __name__ == "__main__":
    sys.exit(main())
