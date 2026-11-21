"""Stage-3 import converters (R3C) on hand-built export objects."""

from datetime import date, datetime, timezone

from app.imports import import_stage1, import_stage2

DOMAIN = "acme-robotics.test"
RESEARCHED = "2026-03-01T09:00:00+00:00"
FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")


def stage1_dossier(state="ready", researched=RESEARCHED):
    cite = {"url": f"https://{DOMAIN}/about", "excerpt": "Acme Robotics is headquartered in Lisbon.",
            "provider": "nimble"}
    fields = {name: {"value": None, "citations": []} for name in FIELD_NAMES}
    fields["hq_city"] = {"value": "Lisbon", "citations": [cite]}
    return {"id": "d_1", "domain": DOMAIN, "state": state, "researched_at": researched,
            "spent_units": 47, "fields": fields}


def test_stage1_ready_dossier_is_one_build_with_one_version_per_cited_url():
    (record,) = import_stage1(stage1_dossier(), DOMAIN)
    assert record.ok and record.spent_units == 47 and record.index == 1
    assert record.time == datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    assert [v.url for v in record.versions] == [f"https://{DOMAIN}/about"]
    assert record.versions[0].true_from is None


def test_stage1_without_researched_at_or_not_ready_has_no_record():
    assert import_stage1(stage1_dossier(researched=None), DOMAIN) == ()
    assert import_stage1(stage1_dossier(state="failed"), DOMAIN) == ()


def test_stage2_candidates_take_true_from_from_published_utc_date():
    item = {"id": "d_2", "domain": DOMAIN, "state": "ready", "researched_at": RESEARCHED,
            "spent_units": 30,
            "candidates": {"hq_city": [{"value": "Lisbon", "url": f"https://{DOMAIN}/about",
                                        "excerpt": "Acme Robotics is headquartered in Lisbon.",
                                        "provider": "nimble", "kind": "own",
                                        "published_at": "2026-01-10T23:30:00-05:00"}],
                           **{n: [] for n in FIELD_NAMES if n != "hq_city"}}}
    (record,) = import_stage2(item, DOMAIN)
    assert record.versions[0].true_from == date(2026, 1, 11)
    assert record.versions[0].candidates["hq_city"][0].value == "Lisbon"
