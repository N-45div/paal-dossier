#!/usr/bin/env python3
"""Move running Codex seats to another OpenAI model without recreating them.

    python3 model-proxy.py [port]        # default 8791, forwards to https://api.openai.com

Band fixes each seat's model when the seat is created and has no command to change it, and a
new seat would get a new room identity the other seats do not know. This proxy sits between
the seats and OpenAI: Codex reaches it through a model provider in ~/.codex/config.toml, and
the proxy rewrites the request's `model` to the id in the target file (default
~/.paal-model-target), re-read on every request; lines of `<JAM_SESSION>=<model>` give each
seat its own model. An empty or missing file passes requests through unchanged, so the switch can be armed ahead of time and flipped at a stage boundary.
The seat's own Authorization header is forwarded as is; the proxy holds no key. Responses,
including streamed ones, pass through unchanged. Standard library only.

To move the seats to another provider that serves the OpenAI Responses API (Meta's Model API
at https://api.meta.ai does), run a second instance with MODEL_PROXY_UPSTREAM set to it and
MODEL_PROXY_KEY_FILE naming an env file that holds MODEL_PROXY_KEY_VAR (default META_API_KEY):
the proxy then replaces the seat's OpenAI credentials with that key, which never reaches the seat.
MODEL_PROXY_DROP_FIELDS lists request fields the upstream rejects (comma-separated; a dotted
name such as text.verbosity drops a nested key).
"""
import http.server
import json
import os
import re
import sys
import urllib.error
import urllib.request

UPSTREAM = os.environ.get("MODEL_PROXY_UPSTREAM", "https://api.openai.com")
TARGET_FILE = os.path.expanduser(os.environ.get("MODEL_PROXY_TARGET", "~/.paal-model-target"))
DROP = [f for f in os.environ.get("MODEL_PROXY_DROP_FIELDS", "").split(",") if f]
MAX_OUTPUT = int(os.environ.get("MODEL_PROXY_MAX_OUTPUT") or 0)
OPENAI_ONLY = ("authorization", "openai-organization", "openai-project", "chatgpt-account-id")


def load_key():
    path = os.environ.get("MODEL_PROXY_KEY_FILE")
    if not path:
        return ""
    var = os.environ.get("MODEL_PROXY_KEY_VAR", "META_API_KEY")
    text = open(os.path.expanduser(path), encoding="utf-8").read()
    m = re.search(r"""^%s=['"]?([^'"\n]+)""" % re.escape(var), text, re.M)
    if not m:
        sys.exit(f"no {var} in {path}")
    return m.group(1)


KEY = load_key()


def seat_of(port):
    """JAM_SESSION of the local process that owns the client socket on `port` (Linux only)."""
    try:
        inode = next((f[9] for f in (l.split() for l in open("/proc/net/tcp"))
                      if len(f) > 9 and f[1] == "0100007F:%04X" % port), None)
    except OSError:
        return ""
    if not inode:
        return ""
    want = f"socket:[{inode}]"
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            if "codex" not in open(f"/proc/{pid}/comm").read():
                continue
            if any(os.readlink(f"/proc/{pid}/fd/{fd}") == want for fd in os.listdir(f"/proc/{pid}/fd")):
                env = open(f"/proc/{pid}/environ", "rb").read().split(b"\0")
                return next((e[12:].decode() for e in env if e.startswith(b"JAM_SESSION=")), "")
        except OSError:
            continue
    return ""


def target(seat=""):
    """The model for a seat. The target file holds one model id for every seat, or lines of
    `<JAM_SESSION>=<model>` with an optional `*=<model>` default; re-read on every request."""
    try:
        lines = [l.strip() for l in open(TARGET_FILE, encoding="utf-8") if l.strip()]
    except OSError:
        return ""
    pairs = dict(l.split("=", 1) for l in lines if "=" in l)
    plain = [l for l in lines if "=" not in l]
    return pairs.get(seat) or pairs.get("*") or (plain[0] if plain else "")


TRANSLATE = os.environ.get("MODEL_PROXY_TRANSLATE") == "1"
# With translation on, a turn that ends without a tool call is checked once: the model is asked
# whether anything it said it would do is still undone (MODEL_PROXY_END_CHECK=0 turns this off).
CHECK_END = TRANSLATE and os.environ.get("MODEL_PROXY_END_CHECK", "1") == "1"
END_CHECK = ("Harness check before your turn ends: plain assistant text reaches nobody. If your last "
             "message said you would do, verify, send, report, reply or hand off anything that you have "
             "not yet done with a tool call in this turn, do it now with tool calls (send replies to "
             "other agents with the room tools). A turn ends only when the work it started is finished "
             "and reported with the room tools, or explicitly settled with the no-reply tool. If "
             "everything is done and every needed reply has been sent, answer with only the word: done.")
KEEP_INPUT = ("message", "function_call", "function_call_output",
              "custom_tool_call", "custom_tool_call_output")


PROMISE = re.compile(r"\b(now|next|i'll|i will|let me|going to|about to|continu\w*|proceed\w*|resum\w*)\b"
                     r"|[—–-]\s*(and\s+)?\w+ing\b", re.I)
REPLY_TOOLS = ("jam_reply_to_message", "jam_no_reply")
NO_REPLY_CHECK = ("Harness check before your turn ends: in this turn you have not called the room reply "
                  "tool or the no-reply tool, so nobody has heard from you and nobody will wake you. Do "
                  "not answer with text. Either continue the work you started now with tool calls, or "
                  "send your current status and what you will do next to whoever is waiting on you with "
                  "the room reply tool, mentioning them.")
LAST_CHECK = {}


def promises_more(items):
    """True when the turn's closing message reads as an intention ("now sending ...")."""
    text = " ".join(c.get("text", "") for it in items if it.get("type") == "message"
                    for c in it.get("content") or [] if isinstance(c, dict))
    return bool(PROMISE.search(text))


def replied_this_turn(data):
    """True when a room reply or no-reply call follows the latest user message. A Band seat's
    turn always ends with one of them; a turn without either was cut short."""
    items = [i for i in (data.get("input") or []) if isinstance(i, dict)]
    start = max((n for n, i in enumerate(items) if i.get("role") == "user"), default=-1)
    return any(i.get("type") == "function_call"
               and any(t in (i.get("name", "") + (i.get("arguments") or "")) for t in REPLY_TOOLS)
               for i in items[start + 1:])


CHECKS_PER_WINDOW = int(os.environ.get("MODEL_PROXY_END_CHECKS", "4"))


def check_allowed(data, window=600):
    """At most MODEL_PROXY_END_CHECKS end checks (default 4) per conversation in any ten
    minutes, so it can never loop. A restart starts a new conversation and loses the seat's
    context, so keeping a turn alive here is worth several re-asks."""
    import time
    key = data.get("prompt_cache_key") or "default"
    now = time.time()
    recent = [t for t in LAST_CHECK.get(key, []) if now - t < window]
    if len(recent) >= CHECKS_PER_WINDOW:
        LAST_CHECK[key] = recent
        return False
    LAST_CHECK[key] = recent + [now]
    return True


def adapter_note():
    """Optional harness note for a model that does not know Codex's conventions (text of
    MODEL_PROXY_NOTE_FILE, re-read on every request; appended to the instructions)."""
    path = os.environ.get("MODEL_PROXY_NOTE_FILE")
    try:
        return open(os.path.expanduser(path), encoding="utf-8").read().strip() if path else ""
    except OSError:
        return ""


def text_of(output):
    """A tool output as plain text (the upstream may not take content lists)."""
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        parts = [c.get("text", "[image omitted]" if "image" in str(c.get("type")) else "")
                 for c in output if isinstance(c, dict)]
        return "\n".join(p for p in parts if p)
    return json.dumps(output)


def to_upstream(data):
    """Rewrite a Codex request for an endpoint that takes only plain function tools.

    Codex sends its tools inside an `additional_tools` input item, grouped in namespaces, and
    runs commands through a freeform `custom` tool (`exec`, which takes JavaScript). Those
    become plain function tools (a custom tool takes its text as the `input` argument), past
    calls and outputs are rewritten to match, and items only OpenAI can read (reasoning blobs,
    compaction records) are dropped. Returns {upstream name: (namespace, name, is_custom)}."""
    tools_in, items = list(data.get("tools") or []), []
    raw = data.get("input")
    for it in raw if isinstance(raw, list) else []:
        if isinstance(it, dict) and it.get("type") == "additional_tools":
            tools_in += it.get("tools") or []
        else:
            items.append(it)
    flat, out_tools = {}, []

    def add(t, ns):
        if t.get("type") == "namespace":
            for sub in t.get("tools") or []:
                add(sub, t.get("name"))
            return
        if t.get("type") not in ("function", "custom") or not t.get("name"):
            return
        name = t["name"]
        up = name if name not in flat else f"{ns}__{name}"
        custom = t["type"] == "custom"
        flat[up] = (ns, name, custom)
        desc = t.get("description") or name
        if custom:
            desc += "\n\nPass the raw input text (for exec: the JavaScript source) as the `input` string."
            params = {"type": "object", "required": ["input"],
                      "properties": {"input": {"type": "string", "description": "Raw tool input text."}}}
        else:
            params = t.get("parameters") or {"type": "object", "properties": {}}
        out_tools.append({"type": "function", "name": up, "description": desc, "parameters": params})

    for t in tools_in:
        if isinstance(t, dict):
            add(t, None)
    by_key = {(ns, n): up for up, (ns, n, _) in flat.items()}
    by_name = {}
    for up, (_, n, _) in flat.items():
        by_name.setdefault(n, up)

    def up_name(it):
        return by_key.get((it.get("namespace"), it.get("name"))) or by_name.get(it.get("name")) or it.get("name")

    # Meta wants exactly one output per call. Codex history can repeat a call or its output
    # (seen after a retried turn), so the first of each is kept and repeats are dropped.
    calls, answered, new = set(), set(), []
    for it in items:
        if not isinstance(it, dict):
            continue
        kind = it.get("type") or ("message" if "role" in it else None)
        if kind not in KEEP_INPUT:
            continue
        if kind == "message":
            content = it.get("content")
            if isinstance(content, list):
                content = [c for c in content if isinstance(c, dict)
                           and c.get("type") in ("input_text", "output_text", "input_image")]
            new.append({"type": "message", "role": it.get("role"), "content": content})
        elif kind in ("function_call", "custom_tool_call"):
            if it.get("call_id") in calls:
                continue
            args = it.get("arguments") if kind == "function_call" else json.dumps({"input": it.get("input", "")})
            calls.add(it.get("call_id"))
            new.append({"type": "function_call", "call_id": it.get("call_id"), "name": up_name(it),
                        "arguments": args or "{}"})
        elif it.get("call_id") in calls and it.get("call_id") not in answered:
            answered.add(it.get("call_id"))
            new.append({"type": "function_call_output", "call_id": it.get("call_id"),
                        "output": text_of(it.get("output"))})
    if isinstance(raw, list):
        data["input"] = new
    note = adapter_note()
    if note:
        data["instructions"] = ((data.get("instructions") or "") + "\n\n" + note).strip()
    if out_tools:
        data["tools"] = out_tools
    else:
        data.pop("tools", None)
        data.pop("tool_choice", None)
    return flat


def from_upstream(item, flat):
    """Turn an upstream function call back into the tool call Codex sent the tool as."""
    if not (isinstance(item, dict) and item.get("type") == "function_call" and item.get("name") in flat):
        return item
    ns, name, custom = flat[item["name"]]
    if custom:
        try:
            text = json.loads(item.get("arguments") or "{}").get("input", "")
        except (ValueError, AttributeError):
            text = item.get("arguments") or ""
        out = {"type": "custom_tool_call", "id": item.get("id"), "call_id": item.get("call_id"),
               "name": name, "input": text, "status": item.get("status", "completed")}
    else:
        out = dict(item, name=name)
    if ns and (ns != "functions" or os.environ.get("MODEL_PROXY_NS_FUNCTIONS") == "1"):
        out["namespace"] = ns
    return out


def translate_event(ev, flat, custom_ids):
    """One streamed event mapped back for Codex; None drops it."""
    kind = ev.get("type", "")
    item = ev.get("item")
    if isinstance(item, dict):
        if item.get("type") == "function_call" and flat.get(item.get("name"), (0, 0, False))[2]:
            custom_ids.add(item.get("id"))
        ev["item"] = from_upstream(item, flat)
    if kind.startswith("response.function_call_arguments.") and ev.get("item_id") in custom_ids:
        return None   # a custom tool's input arrives whole in output_item.done
    if ev.get("name") in flat:
        ev["name"] = flat[ev["name"]][1]
    resp = ev.get("response")
    if isinstance(resp, dict) and isinstance(resp.get("output"), list):
        resp["output"] = [from_upstream(o, flat) for o in resp["output"]]
    return ev


class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def _chunk(self, data):
        if data:
            self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
            self.wfile.flush()

    def _relay_translated(self, resp, flat, upstream_data=None):
        """Pass the upstream response on with its tool calls mapped back (SSE or JSON)."""
        if "json" in (resp.headers.get("content-type") or ""):
            body = resp.read()
            try:
                data = json.loads(body)
                if isinstance(data.get("output"), list):
                    data["output"] = [from_upstream(o, flat) for o in data["output"]]
                    body = json.dumps(data).encode()
            except (ValueError, AttributeError):
                pass
            self._chunk(body)
            return
        state = self._pump(resp, flat, offset=0, first=True)
        held = state["completed"]
        if held is None:
            return
        if (CHECK_END and upstream_data is not None and not state["tool"]
                and held.get("response", {}).get("status", "completed") == "completed"
                and (promises_more(state["items"]) or not replied_this_turn(upstream_data))
                and check_allowed(upstream_data)):
            note = END_CHECK if replied_this_turn(upstream_data) else NO_REPLY_CHECK
            follow = self._end_check(upstream_data, state["items"], note)
            if follow is not None:
                second = self._pump(follow, flat, offset=len(state["items"]), first=False)
                if second["completed"] is not None:
                    sys.stderr.write(f"end check: {'tool calls' if second['tool'] else 'no tool calls'} after re-ask\n")
                    merged = second["completed"]
                    merged.setdefault("response", {})["output"] = state["items"] + second["items"]
                    held = merged
        self._chunk(b"event: " + held.get("type", "response.completed").encode()
                    + b"\ndata: " + json.dumps(held).encode() + b"\n\n")

    def _pump(self, resp, flat, offset, first):
        """Relay one upstream SSE stream, holding back its completion event.

        Returns the held completion (None if the stream ended otherwise), the finished output
        items, and whether any of them was a tool call. A second stream (the end check) drops
        its start events and shifts output indexes past the first stream's items."""
        state = {"completed": None, "items": [], "tool": False}
        custom_ids, block = set(), []
        while True:
            line = resp.readline()
            if line and line.strip():
                block.append(line)
                continue
            if block:
                out, drop = [], False
                for b in block:
                    if not b.startswith(b"data:"):
                        out.append(b)
                        continue
                    try:
                        ev = translate_event(json.loads(b[5:]), flat, custom_ids)
                    except ValueError:
                        out.append(b)
                        continue
                    if ev is None:
                        drop = True
                        break
                    kind = ev.get("type", "")
                    if kind in ("response.completed", "response.done"):
                        state["completed"], drop = ev, True
                        break
                    if not first and kind in ("response.created", "response.in_progress"):
                        drop = True
                        break
                    if offset and isinstance(ev.get("output_index"), int):
                        ev["output_index"] += offset
                    if kind == "response.output_item.done" and isinstance(ev.get("item"), dict):
                        state["items"].append(ev["item"])
                        if ev["item"].get("type") in ("function_call", "custom_tool_call"):
                            state["tool"] = True
                    out.append(b"data: " + json.dumps(ev).encode() + b"\n")
                if not drop:
                    self._chunk(b"".join(out) + b"\n")
                block = []
            if not line:
                return state

    def _end_check(self, data, items, note=END_CHECK):
        """Ask once more when the model ends its turn: undone promises get done now."""
        said = [c.get("text", "") for it in items if it.get("type") == "message"
                for c in it.get("content") or [] if isinstance(c, dict)]
        follow = dict(data, stream=True)
        follow["input"] = list(data.get("input") or []) + [
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": t}]}
            for t in said if t.strip()] + [
            {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": note}]}]
        body = json.dumps(follow).encode()
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method="POST", headers={
            "content-type": "application/json", "authorization": "Bearer " + KEY,
            "content-length": str(len(body))})
        try:
            resp = urllib.request.urlopen(req, timeout=900)
        except (urllib.error.URLError, OSError) as err:
            sys.stderr.write(f"end check skipped: {err}\n")
            return None
        return resp if resp.status == 200 else None

    def _forward(self, body, flat=None, upstream_data=None):
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "content-length", "accept-encoding", "connection")
                   and not (KEY and k.lower() in OPENAI_ONLY)}
        if KEY:
            headers["authorization"] = "Bearer " + KEY
        if body is not None:
            headers["content-length"] = str(len(body))
        # A rate limit or a busy upstream is waited out here (Retry-After, else backoff, about
        # three minutes in all), so a short limit never ends a seat's turn.
        import time
        waits = [5, 10, 20, 30, 45, 60]
        while True:
            req = urllib.request.Request(UPSTREAM + self.path, data=body, headers=headers,
                                         method=self.command)
            try:
                resp = urllib.request.urlopen(req, timeout=900)
            except urllib.error.HTTPError as err:
                resp = err
            if resp.status not in (429, 502, 503, 529) or not waits:
                break
            try:
                pause = min(float(resp.headers.get("retry-after") or 0), 60) or waits[0]
            except ValueError:
                pause = waits[0]
            waits.pop(0)
            sys.stderr.write(f"upstream {resp.status}, retrying in {pause:.0f}s\n")
            time.sleep(pause)
        self.send_response(resp.status)
        for k, v in resp.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        if flat is not None and resp.status == 200:
            self._relay_translated(resp, flat, upstream_data)
            self.wfile.write(b"0\r\n\r\n")
            return
        while True:
            chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
            if not chunk:
                break
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length") or 0))
        seat = seat_of(self.client_address[1])
        to, flat, sent = target(seat), None, None
        if to and not self.headers.get("content-encoding"):
            try:
                data = json.loads(body)
                if isinstance(data, dict) and "model" in data:
                    sys.stderr.write(f"{self.path} model {data['model']} -> {to} ({seat or 'unknown seat'})\n")
                    data["model"] = to
                    # Some providers default to a small output limit (GLM on Baseten: 4096),
                    # which a long reasoning step uses up; MODEL_PROXY_MAX_OUTPUT raises it.
                    if MAX_OUTPUT and "max_output_tokens" not in data:
                        data["max_output_tokens"] = MAX_OUTPUT
                    for field in DROP:  # "a.b" drops key b inside object a
                        *parents, last = field.split(".")
                        node = data
                        for k in parents:
                            node = node.get(k) if isinstance(node, dict) else None
                        if isinstance(node, dict):
                            node.pop(last, None)
                    if TRANSLATE and self.path.rstrip("/").endswith("/responses"):
                        flat = to_upstream(data)
                        sent = data
                    body = json.dumps(data).encode()
                    if os.environ.get("MODEL_PROXY_DUMP"):
                        open(os.environ["MODEL_PROXY_DUMP"], "wb").write(body)
            except ValueError:
                pass
        elif self.headers.get("content-encoding"):
            sys.stderr.write(f"{self.path} compressed body ({self.headers['content-encoding']}), passed through\n")
        try:
            self._forward(body, flat, sent)
        except (BrokenPipeError, ConnectionResetError):
            pass   # the client hung up after it had what it needed

    def do_GET(self):
        self._forward(None)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
    print(f"model proxy on 127.0.0.1:{port} -> {UPSTREAM}, target from {TARGET_FILE}", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Proxy).serve_forever()
