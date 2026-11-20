"""Per-wall reference grid: each wall can carry its own grid, inspections freeze
the grid they were analysed with, and real dimensions give an estimated m^2."""
from urllib.parse import quote

USER = {"X-User-Name": quote("م. سارة")}


def _upload(client, wall_id, path):
    with open(path, "rb") as f:
        r = client.post("/api/inspections", data={"wall_id": wall_id},
                        files={"image": (path.name, f, "image/jpeg")}, headers=USER)
    assert r.status_code == 201, r.text
    return r.json()


def _cells_in_range(insp, cols, rows):
    letters = {chr(65 + i) for i in range(cols)}
    for r in insp["regions"]:
        for c in r["grid_cells"]:
            assert c[0] in letters and 1 <= int(c[1:]) <= rows, c


def test_wall_without_grid_uses_temporary_default(client, samples):
    w = client.post("/api/walls", json={"code": "W-T"}, headers=USER).json()
    assert w["grid"]["type"] == "temporary" and w["cell_size_m"] is None
    insp = _upload(client, w["id"], samples / "synthetic_wall_T1.jpg")
    assert insp["grid"]["type"] == "temporary"
    assert all(r["area_m2"] is None for r in insp["regions"])


def test_wall_grid_is_used_and_gives_area_in_m2(client, samples):
    body = {"code": "W-G", "grid": {"cols": 10, "rows": 3, "width_m": 8.0, "height_m": 3.0}}
    w = client.post("/api/walls", json=body, headers=USER).json()
    assert w["grid"] == {"cols": 10, "rows": 3, "width_m": 8.0, "height_m": 3.0,
                         "note": "", "type": "wall", "version": 1}
    assert w["cell_size_m"] == [0.8, 1.0]

    insp = _upload(client, w["id"], samples / "synthetic_wall_T1.jpg")
    assert insp["grid"]["cols"] == 10 and insp["grid"]["version"] == 1
    assert insp["regions"]
    _cells_in_range(insp, 10, 3)
    r = insp["regions"][0]
    assert abs(r["area_m2"] - r["area_fraction"] * 24.0) < 0.01

    html = client.get(f"/api/inspections/{insp['id']}/report.html").text
    assert "م²" in html and "خاصة بالجدار" in html


def test_grid_dimensions_must_come_together(client):
    body = {"code": "W-X", "grid": {"cols": 4, "rows": 2, "width_m": 5.0}}
    assert client.post("/api/walls", json=body, headers=USER).status_code == 422
    body["grid"] = {"cols": 27, "rows": 2}  # columns are lettered A..Z
    assert client.post("/api/walls", json=body, headers=USER).status_code == 422


def test_changing_grid_keeps_approved_cases_and_remaps_open_ones(client, samples):
    w = client.post("/api/walls", json={"code": "W-C", "grid": {"cols": 4, "rows": 2}}, headers=USER).json()
    approved = _upload(client, w["id"], samples / "synthetic_wall_T1.jpg")
    for r in approved["regions"]:
        assert client.post(f"/api/inspections/{approved['id']}/regions/{r['id']}/approve",
                           json={}, headers=USER).status_code == 200
    assert client.post(f"/api/inspections/{approved['id']}/approve", json={}, headers=USER).status_code == 200
    open_case = _upload(client, w["id"], samples / "synthetic_wall_T2.jpg")

    # Without apply_to_open: nothing existing changes, only new inspections.
    r = client.put(f"/api/walls/{w['id']}/grid", json={"cols": 12, "rows": 5}, headers=USER)
    assert r.status_code == 200 and r.json()["grid"]["version"] == 2
    assert client.get(f"/api/inspections/{open_case['id']}").json()["grid"]["cols"] == 4

    # With apply_to_open: the open case is re-mapped, the approved one keeps its grid.
    r = client.put(f"/api/walls/{w['id']}/grid",
                   json={"cols": 12, "rows": 5, "apply_to_open": True, "reason": "شبكة اللجنة"}, headers=USER)
    out = r.json()
    assert out["grid"]["version"] == 3
    assert open_case["case_number"] in out["applied_to"]
    assert approved["case_number"] in out["kept_previous_grid"]

    reopened = client.get(f"/api/inspections/{open_case['id']}").json()
    assert reopened["grid"]["cols"] == 12 and reopened["grid"]["version"] == 3
    _cells_in_range(reopened, 12, 5)
    still = client.get(f"/api/inspections/{approved['id']}").json()
    assert still["grid"]["cols"] == 4 and still["status"] == "approved"

    audit = client.get("/api/audit", params={"inspection_id": open_case["id"]}).json()
    assert any(e["field"] == "grid" and e["reason"] == "شبكة اللجنة" for e in audit)


def test_old_database_without_grid_column_is_migrated(tmp_path):
    import sqlite3

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE walls (id VARCHAR(32) PRIMARY KEY, code VARCHAR(64), building_name VARCHAR(200),"
                " location_note TEXT, created_at DATETIME)")
    con.commit(); con.close()

    from app.database.session import init_engine
    from sqlalchemy import inspect

    eng = init_engine(f"sqlite:///{db}")
    assert "grid" in {c["name"] for c in inspect(eng).get_columns("walls")}


def test_apply_current_wall_grid_to_one_case(client, samples):
    w = client.post("/api/walls", json={"code": "W-A"}, headers=USER).json()
    insp = _upload(client, w["id"], samples / "synthetic_wall_T1.jpg")
    assert insp["grid"]["type"] == "temporary"
    client.put(f"/api/walls/{w['id']}/grid", json={"cols": 8, "rows": 4, "width_m": 6, "height_m": 3}, headers=USER)
    assert client.get(f"/api/inspections/{insp['id']}").json()["wall"]["grid"]["version"] == 1

    out = client.post(f"/api/inspections/{insp['id']}/apply-wall-grid", headers=USER).json()
    assert out["grid"]["cols"] == 8 and out["grid"]["type"] == "wall"
    _cells_in_range(out, 8, 4)
    assert out["regions"][0]["area_m2"] is not None


def test_inspection_lists_materials_by_location(client, samples):
    w = client.post("/api/walls", json={"code": "W-M"}, headers=USER).json()
    insp = _upload(client, w["id"], samples / "synthetic_wall_T1.jpg")
    r = next(x for x in insp["regions"] if x["damage_type"] != "uncertain")
    client.patch(f"/api/inspections/{insp['id']}/regions/{r['id']}",
                 json={"materials": ["طين محلي"], "tools": ["مالج"]}, headers=USER)
    rows = client.get(f"/api/inspections/{insp['id']}").json()["materials_by_location"]
    mat = next(x for x in rows if x["name"] == "طين محلي")
    assert mat["kind"] == "material" and f"R{r['index']}" in mat["regions"] and mat["cells"] == r["grid_cells"]
