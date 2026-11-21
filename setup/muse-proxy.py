#!/usr/bin/env python3
"""Let Claude Code seats run on Meta's Muse models when the Claude subscription is limited.

    MUSE_KEY_FILE=~/.meta.env python3 muse-proxy.py [port]      # default 8790

Band starts every Claude Code seat with a Claude model id (`--model claude-...`), which Meta's
Model API does not accept. This proxy listens on 127.0.0.1, forwards the Anthropic Messages
requests to https://api.meta.ai, and rewrites the model id to MUSE_MODEL (default
muse-spark-1.3). Point a seat at it with ANTHROPIC_BASE_URL=http://127.0.0.1:<port> and any
API key; the proxy sends the Meta key itself, so the key never reaches the seat. Responses,
including streamed ones, pass through unchanged. Standard library only.
"""
import http.server
import json
import os
import re
import sys
import urllib.error
import urllib.request

UPSTREAM = os.environ.get("MUSE_UPSTREAM", "https://api.meta.ai")
MODEL = os.environ.get("MUSE_MODEL", "muse-spark-1.3")
# Request fields the Muse endpoint rejects; dropped before forwarding.
DROP = [f for f in os.environ.get("MUSE_DROP_FIELDS", "").split(",") if f]


def load_key():
    path = os.path.expanduser(os.environ.get("MUSE_KEY_FILE", "~/.meta.env"))
    text = open(path, encoding="utf-8").read()
    m = re.search(r"""^META_API_KEY=['"]?([^'"\n]+)""", text, re.M)
    if not m:
        sys.exit(f"no META_API_KEY in {path}")
    return m.group(1)


KEY = load_key()


class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def _forward(self, body):
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "content-length", "x-api-key", "authorization",
                                        "accept-encoding", "connection")}
        headers["x-api-key"] = KEY
        if body is not None:
            headers["content-length"] = str(len(body))
        req = urllib.request.Request(UPSTREAM + self.path, data=body, headers=headers,
                                     method=self.command)
        try:
            resp = urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as err:
            resp = err
        self.send_response(resp.status)
        for k, v in resp.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        while True:
            chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
            if not chunk:
                break
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length") or 0))
        try:
            data = json.loads(body)
            if isinstance(data, dict) and "model" in data:
                data["model"] = MODEL
                for field in DROP:
                    data.pop(field, None)
                body = json.dumps(data).encode()
        except ValueError:
            pass
        self._forward(body)

    def do_GET(self):
        self._forward(None)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    print(f"muse proxy on 127.0.0.1:{port} -> {UPSTREAM} as {MODEL}", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Proxy).serve_forever()
