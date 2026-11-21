"""Excel / GeoJSON export (challenge step 10): approved inspections only."""
from __future__ import annotations

import io
import json
from urllib.parse import quote

import pytest
from openpyxl import load_workbook

from app.services import export as ex

USER = {"X-User-Name": quote("م. سارة")}


def _region(i, poly, **over):
    r = {
        "id": f"r{i}", "index": i, "damage_type": "crack", "damage_label_ar": "تشقق", "polygon": poly,
        "confidence": 0.8, "confidence_source": "heuristic_uncalibrated", "area_fraction": 0.0123,
        "grid_cells": ["A1", "B2"], "description": "وصف", "priority": "high",
        "status": "approved", "status_label_ar": "معتمدة", "source": "agent",
        "needs_field_inspection": True, "note": "", "treatment_id": "t1",
        "materials": ["مونة طينية (طين، رمل، ماء)", "ماء"], "tools": ["مالج"],
    }
    r.update(over)
    return r


TREATMENTS = {
    "t1": {
        "id": "t1", "title_ar": "ملء الشقوق", "approval": "demo_unapproved",
        "approval_label_ar": "تجريبية غير معتمدة",
        "sources": [{"title": "Preservation Brief 5", "publisher": "NPS", "year": "1978", "locator": "p.7", "quote": "q"}],
    }
}


def _data(**over):
    d = {
        "case_number": "HCC-2026-0001", "wall": {"id": "w", "code": "W-1", "building_name": "مبنى"},
        "captured_at": "2026-01-10T09:00:00", "status": "approved", "width": 2000, "height": 1000,
        "approved_by": "م. سارة", "approved_at": "2026-11-21T01:00:00+00:00", "expert_notes": "ملاحظة",
        "analysis": {"detector": {"name": "heuristic", "validated": False}},
        "summary": {"total": 1, "field_inspection": 1},
        "regions": [_region(1, [[0.1, 0.1], [0.1, 0.5], [0.4, 0.5]])],
    }
    d.update(over)
    return d


# ------------------------------------------------------------------ GeoJSON
def test_geojson_ring_is_closed_counter_clockwise_and_keeps_aspect():
    # Clockwise input in image space (y down); width 2000, height 1000 -> aspect 0.5.
    g = ex.build_geojson(_data(), TREATMENTS)
    ring = g["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    assert ex._signed_area(ring[:-1]) > 0  # RFC 7946: exterior ring counter-clockwise
    ys = sorted({p[1] for p in ring})
    assert ys == [0.25, 0.45]  # (1 - 0.5) * 0.5 and (1 - 0.1) * 0.5: y flipped, scaled by aspect


def test_geojson_states_that_coordinates_are_not_geographic():
    g = ex.build_geojson(_data(), TREATMENTS)
    assert g["hcc"]["coordinate_system"] == "wall_image_plane"
    assert "ليست إحداثيات جغرافية" in g["hcc"]["coordinate_warning_ar"]
    assert "NOT real-world" in g["hcc"]["coordinate_warning_en"]
    json.loads(ex.geojson_text(g))  # serializes


def test_geojson_properties_carry_treatment_and_source():
    p = ex.build_geojson(_data(), TREATMENTS)["features"][0]["properties"]
    assert p["region"] == "R1" and p["priority_ar"] == "عالية"
    assert p["treatment_title_ar"] == "ملء الشقوق"
    assert p["treatment_approval"] == "demo_unapproved"
    assert p["treatment_sources"][0]["locator"] == "p.7"
    assert p["materials"] == ["مونة طينية (طين، رمل، ماء)", "ماء"]  # comma inside an item stays whole


def test_geojson_region_without_polygon_has_null_geometry():
    d = _data(regions=[_region(1, [[0.1, 0.1]])])
    assert ex.build_geojson(d, TREATMENTS)["features"][0]["geometry"] is None


# -------------------------------------------------------------- approval gate
def test_exports_refuse_unapproved_inspection():
    for d in (_data(status="in_review"), _data(status="returned"), _data(status="rejected_quality")):
        with pytest.raises(ex.NotApproved):
            ex.build_geojson(d, TREATMENTS)
        with pytest.raises(ex.NotApproved):
            ex.build_xlsx(d, [], TREATMENTS)


def test_exports_refuse_when_a_region_is_not_approved():
    d = _data(regions=[_region(1, [[0, 0], [1, 0], [1, 1]], status="edited")])
    with pytest.raises(ex.NotApproved):
        ex.build_xlsx(d, [], TREATMENTS)


# --------------------------------------------------------------------- Excel
def _open(raw: bytes):
    return load_workbook(io.BytesIO(raw))


def test_xlsx_has_three_rtl_sheets_with_region_values():
    audit = [{"at": "2026-11-21T01:41:00", "user": "u", "entity": "region", "action": "update",
              "field": "materials", "old_value": ["a"], "new_value": ["b"], "reason": "سبب"}]
    wb = _open(ex.build_xlsx(_data(), audit, TREATMENTS))
    assert wb.sheetnames == ["الحالة", "المناطق", "سجل التعديلات"]
    assert all(ws.sheet_view.rightToLeft for ws in wb.worksheets)

    regions = wb["المناطق"]
    head = [c.value for c in regions[1]]
    row = dict(zip(head, [c.value for c in regions[2]]))
    assert row["المنطقة"] == "R1" and row["الأولوية"] == "عالية"
    assert row["المعالجة المقترحة"] == "ملء الشقوق"
    assert row["المواد"] == "مونة طينية (طين، رمل، ماء)\nماء"
    assert "p.7" in row["المرجع"]
    assert regions["D2"].number_format == "0%"

    log = wb["سجل التعديلات"]
    assert [c.value for c in log[2]][:5] == ["2026-11-21 01:41 UTC", "u", "المنطقة", "تعديل", "المواد"]


def test_xlsx_case_sheet_lists_approver_and_warnings():
    wb = _open(ex.build_xlsx(_data(), [], TREATMENTS))
    cells = {r[0].value: r[1].value for r in wb["الحالة"].iter_rows(min_row=2) if r[0].value != "تنبيه"}
    assert cells["اعتمدها"] == "م. سارة" and cells["تاريخ الاعتماد"] == "2026-11-21 01:00 UTC"
    notes = " ".join(r[1].value for r in wb["الحالة"].iter_rows(min_row=2) if r[0].value == "تنبيه")
    assert "لم يُقيَّم" in notes and "غير معتمدة" in notes


def test_xlsx_keeps_formula_like_text_as_text_and_strips_control_chars():
    d = _data(regions=[_region(1, [[0, 0], [1, 0], [1, 1]], description='=HYPERLINK("http://x")', note="ملاحظة\x07")])
    ws = _open(ex.build_xlsx(d, [], TREATMENTS))["المناطق"]
    head = [c.value for c in ws[1]]
    row = dict(zip(head, ws[2]))
    assert row["الوصف"].value == '=HYPERLINK("http://x")' and row["الوصف"].data_type == "s"
    assert row["ملاحظة المختص"].value == "ملاحظة"


def test_report_and_export_share_the_same_labels():
    from app.models import enums
    from app.reports import generator

    assert generator.PRIORITY_AR is enums.PRIORITY_AR
    assert generator.CONF_SOURCE_AR is enums.CONF_SOURCE_AR


# ------------------------------------------------------------------ endpoints
def _wall(client):
    r = client.post("/api/walls", json={"code": "W-EXP", "building_name": "قصر (مثال)"}, headers=USER)
    assert r.status_code == 201, r.text
    return r.json()


def test_export_endpoints_require_approval_then_return_files(client, samples):
    w = _wall(client)
    path = samples / "synthetic_wall_T1.jpg"
    with open(path, "rb") as f:
        r = client.post("/api/inspections", data={"wall_id": w["id"]}, files={"image": (path.name, f, "image/jpeg")}, headers=USER)
    assert r.status_code == 201, r.text
    iid = r.json()["id"]

    # Not approved yet: both exports are refused with a clear Arabic message.
    for kind in ("xlsx", "geojson"):
        res = client.get(f"/api/inspections/{iid}/export.{kind}")
        assert res.status_code == 409
        assert "اعتماد" in res.json()["detail"]

    assert client.post(f"/api/inspections/{iid}/approve", json={"reason": "نهائي"}, headers=USER).status_code == 200

    res = client.get(f"/api/inspections/{iid}/export.geojson")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/geo+json")
    assert "-regions.geojson" in res.headers["content-disposition"]
    g = res.json()
    assert g["type"] == "FeatureCollection" and g["features"]
    assert g["hcc"]["approved_by"] == "م. سارة"
    assert g["hcc"]["coordinate_system"] == "wall_image_plane"

    res = client.get(f"/api/inspections/{iid}/export.xlsx")
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"]
    wb = load_workbook(io.BytesIO(res.content))
    assert wb.sheetnames == ["الحالة", "المناطق", "سجل التعديلات"]
    assert wb["المناطق"].max_row - 1 == len(g["features"])
    # The approval itself is in the exported audit sheet.
    actions = {row[3].value for row in wb["سجل التعديلات"].iter_rows(min_row=2)}
    assert "اعتماد" in actions

    # Editing after approval revokes it, so the export closes again.
    region = client.get(f"/api/inspections/{iid}").json()["regions"][0]
    client.patch(f"/api/inspections/{iid}/regions/{region['id']}", json={"note": "تعديل"}, headers=USER)
    assert client.get(f"/api/inspections/{iid}/export.xlsx").status_code == 409


def test_export_unknown_inspection_is_404(client):
    assert client.get("/api/inspections/nope/export.xlsx").status_code == 404
    assert client.get("/api/inspections/nope/export.geojson").status_code == 404
