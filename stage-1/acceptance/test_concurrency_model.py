"""Reproducible HTTP histories checked against a small independent serial model."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import random
import threading
import time

import pytest

from conftest import NOW, SEED

DOMAIN = "halvorsen-robotics.test"
EMAIL = "parallel@example.com"
PASSWORD = "correct horse"
ADA = "ada@example.com"
BOB = "bob@example.com"
RESET = {"now": NOW, "users": [SEED["users"][0]]}


@dataclass(frozen=True, repr=False)
class Event:
    kind: str
    token: str | None
    start: int
    end: int
    status: int
    body: object


def serial_transition(state, event, imported_token):
    """Return the next abstract state, or None if this response cannot occur."""
    users, tokens, dossier = state
    users, tokens = dict(users), set(tokens)
    body = event.body
    if event.kind == "reset":
        if event.status != 204:
            return None
        return ((ADA, "u_ada"),), frozenset(), None
    if event.kind == "import":
        if event.status != 204:
            return None
        return tuple(sorted(((ADA, "u_ada"), (BOB, "u_bob")))), frozenset([imported_token]), None
    if event.kind == "signup":
        if EMAIL in users:
            if event.status != 409 or body.get("error", {}).get("code") != "email_taken":
                return None
        else:
            if event.status != 201 or not isinstance(body.get("user_id"), str) or not isinstance(body.get("token"), str):
                return None
            users[EMAIL] = body["user_id"]
            tokens.add(body["token"])
    elif event.kind in ("login", "login_signup"):
        email = BOB if event.kind == "login" else EMAIL
        if email not in users:
            if event.status != 401 or body.get("error", {}).get("code") != "unauthenticated":
                return None
        else:
            if event.status != 200 or body.get("user_id") != users[email] or not isinstance(body.get("token"), str):
                return None
            tokens.add(body["token"])
    elif event.kind in ("create", "refresh"):
        if event.token not in tokens:
            if event.status != 401 or body.get("error", {}).get("code") != "unauthenticated":
                return None
        elif event.kind == "refresh" and dossier is None:
            if event.status != 404 or body.get("error", {}).get("code") != "not_found":
                return None
        elif event.kind == "create" and dossier is None:
            if event.status != 202 or body.get("domain") != DOMAIN or body.get("state") != "building" or not isinstance(body.get("dossier_id"), str):
                return None
            dossier = body["dossier_id"]
        else:
            expected_status = 200 if event.kind == "create" else 202
            if event.status != expected_status or body.get("domain") != DOMAIN or body.get("dossier_id") != dossier:
                return None
            if event.kind == "refresh" and body.get("state") != "building":
                return None
    else:
        raise AssertionError("unknown history operation")
    return tuple(sorted(users.items())), frozenset(tokens), dossier


def admits_serial_order(events, imported_token, start_token, observation):
    """Find a serial order respecting every non-overlapping request interval."""
    n = len(events)
    before = [sum(1 << j for j, other in enumerate(events) if j != i and other.end <= event.start)
              for i, event in enumerate(events)]
    initial = (((ADA, "u_ada"),), frozenset([start_token]), None)
    visited = set()

    def explore(mask, state):
        if mask == (1 << n) - 1:
            users, tokens, dossier = state
            return (dict(users) == observation["users"] and dossier == observation["dossier"]
                    and all((token in tokens) == valid for token, valid in observation["tokens"].items()))
        key = (mask, state)
        if key in visited:
            return False
        visited.add(key)
        for i, event in enumerate(events):
            if mask & (1 << i) or before[i] & ~mask:
                continue
            next_state = serial_transition(state, event, imported_token)
            if next_state is not None and explore(mask | (1 << i), next_state):
                return True
        return False

    return explore(0, initial)


def setup_round(c):
    assert c.request("POST", "/_test/reset", json=SEED, timeout=10).status_code == 204
    imported_token = c.login()
    response = c.request("GET", "/_test/export", timeout=10)
    assert response.status_code == 200
    snapshot = response.json()
    assert c.request("POST", "/_test/reset", json=RESET, timeout=10).status_code == 204
    return snapshot, imported_token, c.login()


def observe(c, events, imported_token, start_token):
    tokens = {imported_token, start_token}
    for event in events:
        if event.kind in ("signup", "login", "login_signup") and event.status in (200, 201):
            tokens.add(event.body["token"])
    # Probe old tokens before observer logins can issue new ones.
    valid = {}
    for token in tokens:
        response = c.request("GET", "/dossiers", headers=c.auth(token))
        assert response.status_code in (200, 401)
        valid[token] = response.status_code == 200
    ada_token = c.login()
    listed = c.request("GET", "/dossiers", headers=c.auth(ada_token))
    assert listed.status_code == 200
    rows = listed.json()["dossiers"]
    assert len(rows) <= 1 and all(row["domain"] == DOMAIN for row in rows)
    dossier = rows[0]["dossier_id"] if rows else None
    users = {ADA: "u_ada"}
    for email in (BOB, EMAIL):
        response = c.request("POST", "/auth/login", json={"email": email, "password": PASSWORD})
        assert response.status_code in (200, 401)
        if response.status_code == 200:
            users[email] = response.json()["user_id"]
    if dossier is not None:
        c.finish(DOMAIN, ada_token, seconds=30)
    return {"users": users, "tokens": valid, "dossier": dossier}


def test_serial_model_rejects_two_completed_duplicates_before_reset():
    """Check the oracle accepts a valid order and rejects an impossible one."""
    a = Event("signup", None, 1, 2, 201, {"user_id": "a", "token": "a-token"})
    b = Event("signup", None, 3, 4, 201, {"user_id": "b", "token": "b-token"})
    reset = Event("reset", None, 5, 6, 204, {})
    observed = {"users": {ADA: "u_ada"}, "tokens": {"initial": False, "a-token": False}, "dossier": None}
    assert admits_serial_order([a, reset], "imported", "initial", observed)
    assert not admits_serial_order([a, b, reset], "imported", "initial", observed)


def test_simultaneous_same_email_signup(client):
    """R1.79 R1.143: two simultaneous signups of one email have a serial outcome."""
    c = client
    barrier = threading.Barrier(2)
    def signup(_):
        barrier.wait(timeout=5)
        return c.request("POST", "/auth/signup", json={"email": EMAIL, "password": PASSWORD, "display_name": "Parallel"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(signup, range(2)))
    assert sorted(r.status_code for r in replies) == [201, 409]
    assert next(r for r in replies if r.status_code == 409).json()["error"]["code"] == "email_taken"


def test_login_after_duplicate_signup(client):
    """R1.79 R1.143: a completed duplicate conflict implies the account is visible to later login."""
    c = client
    for _ in range(20):
        assert c.request("POST", "/_test/reset", json=RESET, timeout=10).status_code == 204
        barrier = threading.Barrier(2)
        def signup():
            barrier.wait(timeout=5)
            return c.request("POST", "/auth/signup", json={"email": EMAIL, "password": PASSWORD, "display_name": "Parallel"})
        statuses = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(signup) for _ in range(2)]
            for future in as_completed(futures):
                response = future.result()
                statuses.append(response.status_code)
                if response.status_code == 409:
                    assert response.json()["error"]["code"] == "email_taken"
                    login = c.request("POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
                    assert login.status_code == 200
        assert sorted(statuses) == [201, 409]


def test_randomized_serial_histories(client):
    """R1.25 R1.79 R1.139 R1.143: concurrent HTTP operations admit a serial history."""
    c = client
    c.control("faults", {"provider": "nimble", "methods": ["search", "extract", "research"], "mode": "error"})
    for seed in (21, 43, 57, 81, 105, 227, 366, 499):
        snapshot, imported_token, start_token = setup_round(c)
        operations = [("signup", None), ("signup", None), ("login", None), ("login_signup", None),
                      ("create", start_token), ("refresh", start_token),
                      ("create", imported_token), ("refresh", imported_token),
                      ("reset", None), ("import", None)]
        randomizer = random.Random(seed)
        randomizer.shuffle(operations)
        delays = [randomizer.random() * .02 for _ in operations]
        barrier = threading.Barrier(len(operations))
        def perform(index):
            kind, token = operations[index]
            barrier.wait(timeout=5)
            time.sleep(delays[index])
            start = time.monotonic_ns()
            if kind == "signup":
                response = c.request("POST", "/auth/signup", json={"email": EMAIL, "password": PASSWORD, "display_name": "Parallel"})
            elif kind in ("login", "login_signup"):
                response = c.request("POST", "/auth/login", json={"email": BOB if kind == "login" else EMAIL, "password": PASSWORD})
            elif kind == "create":
                response = c.request("POST", "/dossiers", headers=c.auth(token, f"create-{seed}-{index}"), json={"domain": DOMAIN})
            elif kind == "refresh":
                response = c.request("POST", "/dossiers/" + DOMAIN + "/refresh", headers=c.auth(token, f"refresh-{seed}-{index}"))
            elif kind == "reset":
                response = c.request("POST", "/_test/reset", json=RESET, timeout=10)
            else:
                response = c.request("POST", "/_test/import", json=snapshot, timeout=10)
            end = time.monotonic_ns()
            return Event(kind, token, start, end, response.status_code, {} if response.status_code == 204 else response.json())
        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            events = list(pool.map(perform, range(len(operations))))
        observed = observe(c, events, imported_token, start_token)
        summary = [(e.kind, e.status, e.start, e.end) for e in events]
        if not admits_serial_order(events, imported_token, start_token, observed):
            pytest.fail(f"No serial order: seed={seed}, history={summary}, users={sorted(observed['users'])}, dossier_present={observed['dossier'] is not None}", pytrace=False)


def test_concurrent_export_and_create_replay(client):
    """R1.94 R1.99 R1.135 R1.139 R1.141 R1.143: export captures write and replay atomically."""
    c = client
    c.control("faults", {"provider": "nimble", "methods": ["search", "extract", "research"], "mode": "error"})
    for seed in range(10):
        assert c.request("POST", "/_test/reset", json=RESET, timeout=10).status_code == 204
        token = c.login()
        barrier = threading.Barrier(2)
        delays = [random.Random(seed).random() * .01, random.Random(seed + 100).random() * .01]
        def run(which):
            barrier.wait(timeout=5)
            time.sleep(delays[which])
            if which == 0:
                return c.request("POST", "/dossiers", headers=c.auth(token, "atomic"), json={"domain": DOMAIN})
            return c.request("GET", "/_test/export", timeout=10)
        with ThreadPoolExecutor(max_workers=2) as pool:
            created, exported = list(pool.map(run, range(2)))
        assert created.status_code == 202 and exported.status_code == 200
        assert c.request("POST", "/_test/import", json=exported.json(), timeout=10).status_code == 204
        listed = c.request("GET", "/dossiers", headers=c.auth(token))
        assert listed.status_code == 200
        rows = listed.json()["dossiers"]
        replay = c.request("POST", "/dossiers", headers=c.auth(token, "atomic"), json={"domain": DOMAIN})
        if rows:
            assert replay.status_code == 200 and replay.json() == created.json()
        else:
            assert replay.status_code == 202
        c.finish(DOMAIN, token, seconds=30)
