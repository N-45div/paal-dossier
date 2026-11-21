"""First file of the run: the service clock follows system time before the first reset.
Must run in a new container, before any reset. Ledger ids named per test.
"""
import datetime as dt

from conftest import SAMPLE_DOMAINS, await_settled, call, parse_ts, start_build


def test_fresh_service_clock_follows_system_time(mock_ready):
    # R1.65, R1.68: before the first reset the clock follows the system time
    r = call("POST", "/auth/signup", body={"email": "fresh@example.com", "password": "correct horse",
                                           "display_name": "Fresh"})
    assert r.status_code == 201, r.text  # 409 here means the container was not fresh
    token = r.json()["token"]
    domain = SAMPLE_DOMAINS[0]
    assert start_build(token, domain).status_code == 202
    d = await_settled(token, domain)
    now = dt.datetime.now(dt.timezone.utc)
    assert abs((parse_ts(d["researched_at"]) - now).total_seconds()) < 300
