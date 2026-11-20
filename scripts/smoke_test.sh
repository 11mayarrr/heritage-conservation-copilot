#!/usr/bin/env bash
# Quick end-to-end check of a running stack (after `docker compose up -d --build`).
#
#   bash scripts/smoke_test.sh                 # checks http://localhost:8080 (frontend + /api via nginx)
#   bash scripts/smoke_test.sh http://host:port
#
# It checks: health, the SPA, wall creation with its own grid, an upload with
# two people in it (faces must be hidden, original not stored), grid cells within
# the wall grid, area in m^2, the stored image, the atlas and the HTML report.
set -euo pipefail

BASE="${1:-http://localhost:8080}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PHOTO="$HERE/tests/fixtures/wall_with_two_visitors.jpg"
USER_HDR="X-User-Name: smoke-test"
CODE="SMOKE-$(date +%s)"
fail() { echo "FAIL: $*" >&2; exit 1; }
json() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }

echo "1/7 waiting for $BASE/api/health"
for i in $(seq 1 60); do
  curl -fsS "$BASE/api/health" >/dev/null 2>&1 && break
  [ "$i" = 60 ] && fail "backend not healthy after 120s"
  sleep 2
done

echo "2/7 frontend (SPA fallback)"
curl -fsS "$BASE/inspections/does-not-exist" | grep -q '<div id="root"' || fail "index.html not served"

echo "3/7 wall with its own grid"
WALL=$(curl -fsS -X POST "$BASE/api/walls" -H "$USER_HDR" -H 'content-type: application/json' \
  -d "{\"code\":\"$CODE\",\"grid\":{\"cols\":8,\"rows\":3,\"width_m\":8,\"height_m\":3}}")
WALL_ID=$(echo "$WALL" | json 'd["id"]')
[ "$(echo "$WALL" | json 'd["grid"]["type"]')" = "wall" ] || fail "wall grid not saved"

echo "4/7 upload a photo with two visitors"
INSP=$(curl -fsS -X POST "$BASE/api/inspections" -H "$USER_HDR" -F "wall_id=$WALL_ID" -F "image=@$PHOTO;type=image/jpeg")
INSP_ID=$(echo "$INSP" | json 'd["id"]')
echo "$INSP" | json '"   status=%s faces_hidden=%s regions=%d" % (d["status"], d["privacy"].get("faces_hidden"), len(d["regions"]))'

echo "5/7 privacy and grid"
echo "$INSP" | python3 -c '
import sys, json
d = json.load(sys.stdin)
assert d["status"] != "rejected_quality", "photo rejected by quality check"
assert d["privacy"]["faces_hidden"] >= 2, "faces not hidden"
assert d["privacy"]["original_stored"] is False, "original stored"
assert d["grid"]["cols"] == 8 and d["grid"]["rows"] == 3, "wall grid not used"
cols = {chr(65 + i) for i in range(8)}
for r in d["regions"]:
    for c in r["grid_cells"]:
        assert c[0] in cols and 1 <= int(c[1:]) <= 3, c
    assert r["area_m2"] is not None, "area_m2 missing"
' || fail "privacy/grid checks"

echo "6/7 stored image, atlas, report"
for p in "image.jpg" "atlas.png" "report.html"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/inspections/$INSP_ID/$p")
  [ "$code" = 200 ] || fail "$p returned $code"
done

echo "7/7 storage persists (re-read the case)"
curl -fsS "$BASE/api/inspections/$INSP_ID" | json 'd["has_image"]' | grep -q True || fail "image missing"

echo "OK: stack works end to end ($BASE, case $(echo "$INSP" | json 'd["case_number"]'))"
