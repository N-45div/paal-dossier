"""Load-test stand-in for app.research: blocking HTTP + CPU work, like the real engine.

Mounted over /srv/app/research by run_load.sh; never part of the delivered image.
"""
import json
import os
import re
import urllib.request


def _search(domain: str) -> str:
    request = urllib.request.Request(
        os.environ["NIMBLE_BASE_URL"].rstrip("/") + "/v2/search",
        data=json.dumps({"query": domain, "max_results": 10, "search_depth": "deep"}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + os.environ.get("NIMBLE_API_KEY", "x")})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode()


def _burn(text: str, rounds: int = 40) -> int:
    count = 0
    for _ in range(rounds):
        count += len(re.findall(r"[A-Z][a-z]+(?: [A-Z][a-z]+)*", text))
    return count


def run_build(domain, spend):
    body = _search(domain)
    spend(5)
    _burn(body)
    return {"ok": True, "fields": {}}
