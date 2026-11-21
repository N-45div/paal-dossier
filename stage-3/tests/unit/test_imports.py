"""Stage-3 import converters (R3C) on hand-built export objects."""

from datetime import datetime, timezone

from app.imports import import_stage1, import_stage2

DOMAIN = "acme-robotics.test"
RESEARCHED = "2026-03-01T09:00:00+00:00"


def stage1_dossier(state="ready", researched=RESEARCHED):
    cite = {"url": f"https://{DOMAIN}/about", "excerpt": "Acme Robotics is headquartered in Lisbon.",
            "provider": "nimble"}
    return {"id": "d_1", "domain": DOMAIN, "state": state, "researched_at": researched,
            "spent_units": 47,
            "fields": {"legal_name": {"value": None, "citations": []},
                       "hq_city": {"value": "Lisbon", "citations": [cite]},
                       "ceo": {"value": None, "citations": []},
                       "founded_year": {"value": None, "citations": []},
                       "headcount_range": {"value": None, "citations": []},
                       "funding_total": {"value": None, "citations": []}}}


def test_stage1_ready_dossier_is_one_build_with_one_version_per_cited_url():
    dossier = import_stage1(stage1_dossier(), DOMAIN)
    assert len(dossier.records) == 1
    record = dossier.records[0]
    assert record.ok and record.spent_units == 47
    assert record.time == datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    assert [v.url for v in record.versions] == [f"https://{DOMAIN}/about"]
    assert record.versions[0].true_from is None


def test_stage1_seeds_one_initial_per_valued_field_at_researched_at():
    dossier = import_stage1(stage1_dossier(), DOMAIN)
    assert [s.field for s in dossier.seeds] == ["hq_city"]
    assert dossier.seeds[0].value == "Lisbon"


def test_stage1_without_researched_at_has_no_records():
    dossier = import_stage1(stage1_dossier(researched=None), DOMAIN)
    assert dossier.records == () and dossier.seeds == ()


def test_stage1_failed_dossier_has_no_records():
    assert import_stage1(stage1_dossier(state="failed"), DOMAIN).records == ()


def test_stage2_candidates_take_true_from_from_published_utc_date():
    item = {"id": "d_2", "domain": DOMAIN, "state": "ready", "researched_at": RESEARCHED,
            "spent_units": 30,
            "candidates": {"hq_city": [{"value": "Lisbon", "url": f"https://{DOMAIN}/about",
                                        "excerpt": "Acme Robotics is headquartered in Lisbon.",
                                        "provider": "nimble", "kind": "own",
                                        "published_at": "2026-01-10T23:30:00-05:00"}],
                           **{n: [] for n in ("legal_name", "ceo", "founded_year",
                                              "headcount_range", "funding_total")}}}
    dossier = import_stage2(item, DOMAIN)
    record = dossier.records[0]
    assert record.versions[0].true_from.isoformat() == "2026-01-11"
    assert record.fields["hq_city"].value == "Lisbon"
