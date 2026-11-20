"""Face anonymization on photos that actually contain people.

Fixtures (tests/fixtures/): a synthetic mud wall with the NASA astronaut
portrait (public domain, from scikit-image's sample data) pasted in, once as two
upright visitors and once tilted 25 degrees. Faces are at known places, so we
can check that those pixels were hidden and that the wall elsewhere was not.
"""
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np
import pytest

FIX = Path(__file__).parent / "fixtures"
USER = {"X-User-Name": quote("م. سارة")}
# Face boxes (x, y, w, h) in the fixtures, from where the portraits were pasted.
TWO_VISITORS = [(170, 300, 120, 110), (840, 335, 100, 95)]
TILTED = [(510, 290, 150, 140)]


def _changed(a: np.ndarray, b: np.ndarray, box) -> float:
    x, y, w, h = box
    return float(np.abs(a[y:y + h, x:x + w].astype(float) - b[y:y + h, x:x + w].astype(float)).mean())


def test_upright_faces_are_hidden_and_wall_is_untouched():
    from app.privacy.anonymizer import anonymize

    img = cv2.imread(str(FIX / "wall_with_two_visitors.jpg"))
    out, info = anonymize(img, method="blur")
    assert info["faces_hidden"] >= 2
    for box in TWO_VISITORS:
        assert _changed(img, out, box) > 10, box
    # A wall patch far from the people must stay identical (damage stays visible).
    assert _changed(img, out, (450, 650, 300, 200)) == 0


def test_tilted_face_hidden_by_yunet():
    from app.privacy.anonymizer import FaceDetector, anonymize

    if FaceDetector().method != "yunet":
        pytest.skip("YuNet model missing: python scripts/download_models.py")
    img = cv2.imread(str(FIX / "wall_with_tilted_visitor.jpg"))
    out, info = anonymize(img)
    assert info["faces_hidden"] >= 1
    assert _changed(img, out, TILTED[0]) > 10


def test_uploaded_photo_is_stored_only_with_faces_hidden(client):
    w = client.post("/api/walls", json={"code": "W-P"}, headers=USER).json()
    path = FIX / "wall_with_two_visitors.jpg"
    with open(path, "rb") as f:
        r = client.post("/api/inspections", data={"wall_id": w["id"]},
                        files={"image": (path.name, f, "image/jpeg")}, headers=USER)
    insp = r.json()
    assert r.status_code == 201 and insp["status"] != "rejected_quality"
    assert insp["privacy"]["faces_hidden"] >= 2 and insp["privacy"]["original_stored"] is False

    stored = cv2.imdecode(np.frombuffer(client.get(f"/api/inspections/{insp['id']}/image.jpg").content, np.uint8),
                          cv2.IMREAD_COLOR)
    original = cv2.imread(str(path))
    assert stored.shape == original.shape
    for box in TWO_VISITORS:
        assert _changed(original, stored, box) > 10, box
