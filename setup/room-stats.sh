#!/usr/bin/env bash
# Teamwork evidence for a Band room: who talked, who handed off to whom, how long it took.
#
#   bash room-stats.sh <room-id> [out.jsonl]
#
# Pages through the whole room as the account owner (`band room messages --json`), saves every
# message as JSON lines, then prints messages per seat, @mention edges between participants,
# rejections and acceptances, and the first-to-last seat message span (the delivery time).
set -euo pipefail
ROOM="${1:?room id}"; OUT="${2:-/tmp/room-$ROOM.jsonl}"
: > "$OUT"; cursor=""
while :; do
  page=$(band room messages "$ROOM" --json ${cursor:+--cursor "$cursor"})
  echo "$page" | jq -c '.messages[]' >> "$OUT"
  cursor=$(echo "$page" | jq -r '.next_cursor // empty')
  [ -n "$cursor" ] || break
done
echo "saved $(wc -l < "$OUT") messages to $OUT"
python3 - "$OUT" <<'P'
import collections, json, re, sys
msgs = [json.loads(l) for l in open(sys.argv[1])]
name = lambda m: m.get("sender_name") or m.get("senderName") or m.get("sender_id") or "?"
kind = lambda m: m.get("message_type") or m.get("messageType") or m.get("type") or "?"
ids = {}
for m in msgs:
    sid = m.get("sender_id") or m.get("senderId")
    if sid: ids[sid] = name(m)
texts = [m for m in msgs if kind(m) == "text"]
print("\nmessages per sender (text):")
for n, c in collections.Counter(name(m) for m in texts).most_common(): print(f"  {c:4}  {n}")
edges = collections.Counter()
for m in texts:
    for to in re.findall(r"@\[\[([0-9a-f-]{36})\]\]", m.get("content", "")):
        edges[(name(m), ids.get(to, to[:8]))] += 1
print("\n@mention handoffs (from -> to):")
for (a, b), c in edges.most_common(): print(f"  {c:4}  {a} -> {b}")
body = lambda m: m.get("content", "")
print(f"\nREJECT verdicts: {sum('REJECT' in body(m) for m in texts)}   ACCEPT verdicts: {sum('ACCEPT' in body(m) for m in texts)}")
times = sorted(m.get("inserted_at") or m.get("created_at") or m.get("insertedAt") or "" for m in texts
               if (m.get("sender_type") or m.get("senderType") or "").lower() == "agent")
if times: print(f"seat messages span: {times[0]}  ->  {times[-1]}")
P
