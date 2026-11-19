from urllib.parse import quote

USER = {"X-User-Name": quote("م. سارة")}


def _wall(client, code="W-001"):
    r = client.post("/api/walls", json={"code": code, "building_name": "قصر سلوى (مثال)"}, headers=USER)
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, wall_id, path, captured_at=None):
    data = {"wall_id": wall_id}
    if captured_at:
        data["captured_at"] = captured_at
    with open(path, "rb") as f:
        r = client.post("/api/inspections", data=data, files={"image": (path.name, f, "image/jpeg")}, headers=USER)
    assert r.status_code == 201, r.text
    return r.json()


def test_health_reports_unvalidated_detector(client):
    h = client.get("/api/health").json()
    assert h["detector"]["validated"] is False
    assert h["original_images_stored"] is False


def test_duplicate_wall_code_rejected(client):
    _wall(client)
    assert client.post("/api/walls", json={"code": "W-001"}).status_code == 409


def test_blurry_image_is_rejected_and_not_stored(client, samples):
    w = _wall(client)
    insp = _upload(client, w["id"], samples / "synthetic_blurry.jpg")
    assert insp["status"] == "rejected_quality"
    assert insp["has_image"] is False and insp["regions"] == []
    assert insp["quality"]["issues"]
    assert client.get(f"/api/inspections/{insp['id']}/image.jpg").status_code == 404


def test_full_review_cycle_with_audit_trail(client, samples):
    w = _wall(client)
    insp = _upload(client, w["id"], samples / "synthetic_wall_T1.jpg", "2026-01-10T09:00:00")
    iid = insp["id"]
    assert insp["status"] == "in_review"
    assert insp["case_number"].startswith("HCC-")
    assert insp["privacy"]["original_stored"] is False
    regions = insp["regions"]
    assert any(r["damage_type"] == "crack" for r in regions)
    for r in regions:
        assert r["status"] == "agent"
        if r["damage_type"] == "uncertain":
            assert r["treatment_id"] is None and r["needs_field_inspection"]

    crack = next(r for r in regions if r["damage_type"] == "crack")
    assert crack["treatment_id"] and crack["materials"] and crack["tools"]

    # Expert changes the type: status becomes edited and the treatment is re-retrieved.
    r = client.patch(f"/api/inspections/{iid}/regions/{crack['id']}",
                     json={"damage_type": "plaster_loss", "note": "تقشر وليس تشقق", "reason": "معاينة"}, headers=USER)
    assert r.status_code == 200, r.text
    edited = r.json()
    assert edited["status"] == "edited" and edited["damage_type"] == "plaster_loss"
    assert edited["treatment_id"] != crack["treatment_id"]

    # Invalid treatment ids are refused (closed library).
    assert client.patch(f"/api/inspections/{iid}/regions/{crack['id']}", json={"treatment_id": "invented"}).status_code == 409

    # Expert adds a region manually and deletes a false positive.
    r = client.post(f"/api/inspections/{iid}/regions", headers=USER, json={
        "damage_type": "material_loss", "polygon": [[0.7, 0.1], [0.8, 0.1], [0.8, 0.2], [0.7, 0.2]],
        "confidence": 0.9, "note": "فقدان واضح"})
    assert r.status_code == 201
    manual = r.json()
    assert manual["source"] == "expert" and manual["confidence_source"] == "expert"
    assert manual["grid_cells"] == ["E1"]
    other = next(x for x in regions if x["id"] != crack["id"])
    assert client.delete(f"/api/inspections/{iid}/regions/{other['id']}", params={"reason": "ظل"}, headers=USER).status_code == 204

    # Region returned for review blocks approval until resolved.
    client.post(f"/api/inspections/{iid}/regions/{manual['id']}/return", json={"reason": "تحقق"}, headers=USER)
    assert client.post(f"/api/inspections/{iid}/approve", json={}, headers=USER).status_code == 409
    client.post(f"/api/inspections/{iid}/regions/{manual['id']}/approve", json={}, headers=USER)

    client.put(f"/api/inspections/{iid}/notes", json={"expert_notes": "يوصى بفحص ميداني للقاعدة"}, headers=USER)
    r = client.post(f"/api/inspections/{iid}/approve", json={"reason": "مراجعة نهائية"}, headers=USER)
    assert r.status_code == 200
    approved = r.json()
    assert approved["status"] == "approved" and approved["approved_by"] == "م. سارة"
    assert all(x["status"] == "approved" for x in approved["regions"])
    assert other["id"] not in {x["id"] for x in approved["regions"]}

    # Editing after approval revokes approval.
    client.patch(f"/api/inspections/{iid}/regions/{manual['id']}", json={"note": "تعديل"}, headers=USER)
    assert client.get(f"/api/inspections/{iid}").json()["status"] == "in_review"

    log = client.get("/api/audit", params={"inspection_id": iid}).json()
    actions = {(e["action"], e["field"]) for e in log}
    assert ("update", "damage_type") in actions
    assert ("delete", "status") in actions
    assert ("approve", "status") in actions
    assert ("approval_revoked", "status") in actions
    change = next(e for e in log if e["field"] == "damage_type")
    assert change["old_value"] == "crack" and change["new_value"] == "plaster_loss"
    assert change["user"] == "م. سارة" and change["reason"] == "معاينة" and change["at"]


def test_outputs_report_atlas_and_anonymized_download(client, samples):
    w = _wall(client)
    iid = _upload(client, w["id"], samples / "synthetic_wall_T1.jpg")["id"]
    img = client.get(f"/api/inspections/{iid}/image.jpg", params={"download": True})
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert "attachment" in img.headers["content-disposition"]
    atlas = client.get(f"/api/inspections/{iid}/atlas.png")
    assert atlas.status_code == 200 and atlas.content[:4] == b"\x89PNG"
    html = client.get(f"/api/inspections/{iid}/report.html").text
    for must in ["رقم الحالة", "W-001", "خريطة التلف", "سجل التعديلات", "مسودة غير معتمدة",
                 "Preservation Brief 5", "data:image/jpeg;base64", "فحص ميداني"]:
        assert must in html, must


def test_invalid_upload_rejected(client):
    w = _wall(client)
    r = client.post("/api/inspections", data={"wall_id": w["id"]}, files={"image": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 422


def test_temporal_comparison(client, samples):
    w = _wall(client)
    a = _upload(client, w["id"], samples / "synthetic_wall_T1.jpg", "2026-01-10T09:00:00")
    b = _upload(client, w["id"], samples / "synthetic_wall_T2.jpg", "2026-06-10T09:00:00")
    # Order of arguments should not matter: older is always "before".
    r = client.post("/api/comparisons", json={"before_id": b["id"], "after_id": a["id"]}, headers=USER)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["before"]["id"] == a["id"]
    assert c["registration"]["ok"]
    s = c["regions"]["summary"]
    assert s["new"] >= 1, s  # the second crack
    assert s["grew"] + s["unchanged"] >= 1, s
    statuses = {i["status"] for i in c["regions"]["items"] if i["damage_type"] == "crack"}
    assert "grew" in statuses, c["regions"]["items"]
    for cand in c["visual_candidates"]["candidates"]:
        assert cand["confidence"] <= 0.3
    assert client.get(f"/api/comparisons/{c['id']}/side_by_side.jpg").status_code == 200

    other = _wall(client, "W-002")
    o = _upload(client, other["id"], samples / "synthetic_wall_T1.jpg")
    assert client.post("/api/comparisons", json={"before_id": a["id"], "after_id": o["id"]}).status_code == 409
