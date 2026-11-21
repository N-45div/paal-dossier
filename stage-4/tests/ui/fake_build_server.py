"""Stub-build service for browser checks (not used by the stage-2 image).

It runs the real stage-2 app with the provider research replaced by a fixed outcome, so a
dossier reaches `building` for about 4 seconds and then `ready`. The outcome has one contested
field (hq_city: "Lisbon" from an own page and "Porto" from a newer news page) and an empty ceo.

Start it from the stage-2 folder, with the Python that has aiohttp installed:

    python tests/ui/fake_build_server.py            # listens on 127.0.0.1:18001
    FAKE_PORT=18002 python tests/ui/fake_build_server.py

Then open http://127.0.0.1:18001/, sign up, and research acme-robotics.test.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STAGE_ROOT))

from aiohttp import web  # noqa: E402

from app import research  # noqa: E402
from app.candidates import Candidate  # noqa: E402
from app.outcome import BuildOutcome, FieldResult  # noqa: E402
from app.server import build_app  # noqa: E402
from app.support import FIELDS  # noqa: E402

PORT = int(os.environ.get("FAKE_PORT", "18001"))
ACME_URL = "https://acme-robotics.test/about"
ACME_EXCERPT = "Acme Robotics, Inc. was founded in 2014 and employs about 120 people."
BUILD_SECONDS = 4


async def fake_run_build(domain, on_spend=None):
    await asyncio.sleep(BUILD_SECONDS)
    fields = research.unknown_fields()
    cites = [{"url": ACME_URL, "excerpt": ACME_EXCERPT, "provider": "nimble"}]
    fields["legal_name"] = FieldResult("Acme Robotics, Inc.", cites)
    fields["founded_year"] = FieldResult(2014, cites)
    fields["headcount_range"] = FieldResult("51-200", cites)
    fields["funding_total"] = FieldResult(12000000, cites)
    fields["hq_city"] = FieldResult("Lisbon", cites)
    candidates = {name: [] for name in FIELDS}
    candidates["legal_name"] = [Candidate("Acme Robotics, Inc.", ACME_URL, ACME_EXCERPT,
                                          "nimble", "own", "2026-02-01T00:00:00+00:00")]
    candidates["hq_city"] = [
        Candidate("Lisbon", ACME_URL, "Acme HQ is in Lisbon.", "nimble", "own", None),
        Candidate("Porto", "https://news.acme-robotics.test/moves",
                  "Acme moved its HQ to Porto.", "tavily", "news", "2026-03-01T00:00:00+00:00"),
    ]
    candidates["founded_year"] = [Candidate(2014, ACME_URL, ACME_EXCERPT, "nimble")]
    candidates["headcount_range"] = [Candidate("51-200", ACME_URL, "about 120 people", "nimble")]
    candidates["funding_total"] = [Candidate(12000000, ACME_URL, "raised 12000000", "nimble")]
    return BuildOutcome(ok=True, spent_units=34, fields=fields, candidates=candidates)


def main() -> None:
    research.run_build = fake_run_build
    web.run_app(build_app(), host="127.0.0.1", port=PORT, access_log=None, print=None)


if __name__ == "__main__":
    main()
