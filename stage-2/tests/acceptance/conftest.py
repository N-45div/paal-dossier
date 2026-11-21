"""Shared helpers for the Dossier stage-1 acceptance suite.

Black-box only: every check goes through the service's HTTP interface (BASE_URL)
and the mock web's admin API (MOCK_URL, MOCK_ADMIN). Nothing reads service source.

Also covers: R1.23-R1.24, R1.102-R1.112 (citation support, provider names, evidence rules),
R1.121 (fixture shape used by reset).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import uuid

import pytest
import requests

from oracle import FIELDS, excerpt_in_prose, split_header, supported_values

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:18210").rstrip("/")
MOCK_URL = os.environ.get("MOCK_URL", "http://127.0.0.1:18220").rstrip("/")
MOCK_ADMIN = os.environ.get("MOCK_ADMIN", "local-admin")
SAMPLE_DOMAINS = [
    d.strip()
    for d in os.environ.get(
        "SAMPLE_DOMAINS", "brightwater-labs.test,ferncliff-foods.test,tidemark-energy.test"
    ).split(",")
    if d.strip()
]
NOW = "2026-03-01T09:00:00+00:00"
PASSWORD = "correct horse"
HEADCOUNT_VALUES = {"1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000",
                    "5001-10000", "10001+"}


def seed_fixture(now: str = NOW, users=None) -> dict:
    if users is None:
        users = [
            {"id": "u_ada", "email": "ada@example.com", "password": PASSWORD, "display_name": "Ada"},
            {"id": "u_bob", "email": "bob@example.com", "password": PASSWORD, "display_name": "Bob"},
        ]
    return {"now": now, "users": users}


# ---- service calls -------------------------------------------------------------

def call(method, path, *, token=None, key=None, body=None, raw=None, timeout=5, headers=None):
    """One HTTP call. key=None sends no Idempotency-Key header; key="" sends an empty one."""
    h = dict(headers or {})
    if token is not None:
        h["Authorization"] = f"Bearer {token}"
    if key is not None:
        h["Idempotency-Key"] = key
    kw = {}
    if raw is not None:
        kw["data"] = raw
        h.setdefault("Content-Type", "application/json")
    elif body is not None:
        kw["json"] = body
    return requests.request(method, BASE_URL + path, headers=h, timeout=timeout, **kw)


def reset_service(fixture: dict | None = None):
    r = call("POST", "/_test/reset", body=fixture or seed_fixture(), timeout=10)
    assert r.status_code == 204, f"reset failed: {r.status_code} {r.text}"


def set_clock(now: str):
    r = call("POST", "/_test/clock", body={"now": now})
    assert r.status_code == 204, f"clock failed: {r.status_code} {r.text}"


def login(email: str, password: str = PASSWORD) -> str:
    r = call("POST", "/auth/login", body={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def new_key() -> str:
    return uuid.uuid4().hex


def start_build(token, domain, key=None, *, raw=None):
    key = new_key() if key is None else key
    if raw is not None:
        return call("POST", "/dossiers", token=token, key=key, raw=raw)
    return call("POST", "/dossiers", token=token, key=key, body={"domain": domain})


def get_dossier(token, domain):
    return call("GET", f"/dossiers/{domain}", token=token)


def await_settled(token, domain, timeout=60.0) -> dict:
    """Poll until the dossier is no longer building; return its body."""
    deadline = time.time() + timeout
    while True:
        r = get_dossier(token, domain)
        assert r.status_code == 200, r.text
        d = r.json()
        if d["state"] != "building":
            return d
        assert time.time() < deadline, f"build for {domain} still running after {timeout}s"
        time.sleep(0.2)


def parse_ts(s: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    assert d.tzinfo is not None, f"timestamp without explicit offset: {s}"
    return d


# ---- mock web calls ------------------------------------------------------------

def mock(method, path, *, body=None, timeout=10):
    return requests.request(method, MOCK_URL + path, headers={"X-Mock-Admin": MOCK_ADMIN},
                            json=body, timeout=timeout)


def mock_reset(epoch: int = 0):
    r = mock("POST", "/_mock/reset", body={"epoch": epoch})
    assert r.status_code == 204, f"mock reset failed: {r.status_code} {r.text}"


def mock_faults(provider, methods, mode, seconds=None):
    body = {"provider": provider, "methods": list(methods), "mode": mode}
    if seconds is not None:
        body["seconds"] = seconds
    r = mock("POST", "/_mock/faults", body=body)
    assert r.status_code == 204, r.text


def mock_weather(on: bool):
    r = mock("POST", "/_mock/weather", body={"on": on})
    assert r.status_code == 204, r.text


def mock_calls() -> list[dict]:
    r = mock("GET", "/_mock/log")
    r.raise_for_status()
    return r.json()["calls"]


def total_cost(calls) -> int:
    return sum(int(c.get("cost") or 0) for c in calls)


def domain_searches(calls, domain, status_ok=True):
    """Searches whose query is exactly the domain and that were answered without an error."""
    return [c for c in calls if c["method"] == "search" and c["query"] == domain
            and (not status_ok or c["status"] == 200)]


def served_index(calls) -> dict:
    """(provider, url) -> list of prose texts that provider served for that URL."""
    idx: dict = {}
    for c in calls:
        for item in c.get("served") or []:
            text = item["text"]
            prose = text if c["method"] == "research" else split_header(text)[1]
            idx.setdefault((c["provider"], item["url"]), []).append(prose)
    return idx


# ---- field checks (section 4 and Appendix A) -----------------------------------

def check_dossier_fields(dossier: dict, domain: str, calls: list[dict]):
    """Every known field cites provider-served prose that supports its value; unknown
    fields are exactly value null and no citations. Returns the number of known fields."""
    assert set(dossier["fields"]) == set(FIELDS), dossier["fields"].keys()
    idx = served_index(calls)
    known = 0
    for name in FIELDS:
        fld = dossier["fields"][name]
        assert set(fld) >= {"value", "status", "citations"}, name
        if fld["value"] is None:
            assert fld["status"] == "unknown", name
            assert fld["citations"] == [], f"{name}: unknown field with citations"
            continue
        known += 1
        assert fld["status"] in ("known", "contested"), name  # stage 2 adds contested
        assert fld["citations"], f"{name}: field without a citation"
        value = fld["value"]
        if name == "founded_year" or name == "funding_total":
            assert isinstance(value, int) and not isinstance(value, bool), (name, value)
        if name == "headcount_range":
            assert value in HEADCOUNT_VALUES, value
        if name in ("legal_name", "hq_city", "ceo", "headcount_range"):
            assert isinstance(value, str) and value == value.strip(), (name, value)
        for c in fld["citations"]:
            assert set(c) >= {"url", "excerpt", "provider"}, (name, c)
            assert c["provider"] in ("nimble", "tavily"), (name, c)
            assert 1 <= len(c["excerpt"]) <= 500, (name, len(c["excerpt"]))
            prose_list = idx.get((c["provider"], c["url"]), [])
            assert any(excerpt_in_prose(p, c["excerpt"]) for p in prose_list), (
                f"{name}: citation not served by {c['provider']} for {c['url']} "
                f"or not from prose: {c['excerpt']!r}")
            got = supported_values(domain, c["excerpt"]).get(name, object())
            assert got == value, (
                f"{name}: citation {c['excerpt']!r} supports {got!r}, not {value!r}")
    return known


@pytest.fixture
def mock_ready():
    """Fail loudly when the mock is not reachable: the suite must not silently skip."""
    r = requests.get(MOCK_URL + "/_mock/health", timeout=5)
    assert r.status_code == 200, "mock web not reachable at MOCK_URL"
    mock_reset(0)
    mock_weather(False)
    yield


@pytest.fixture
def env(mock_ready):
    """Service reset with the seed fixture, mock reset to epoch 0, tokens for Ada and Bob."""
    reset_service()
    ada = login("ada@example.com")
    bob = login("bob@example.com")
    return {"ada": ada, "bob": bob}
