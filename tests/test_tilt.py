"""Camera-tilt estimate (step 1): a rough warning, never a rejection.

Test photos are synthetic: a flat wall pattern warped with a known camera yaw and
pitch, so the true tilt is known. They say nothing about real At-Turaif walls."""
from __future__ import annotations

import math
from urllib.parse import quote

import cv2
import numpy as np
import pytest

from app.vision.tilt import FRONTAL, PARTIAL, STRONG, UNMEASURABLE, estimate_tilt

W, H = 1600, 1200
LONG = max(W, H)
USER = {"X-User-Name": quote("م. سارة")}


def _wall(stagger: bool) -> np.ndarray:
    """Flat wall pattern: long horizontal courses and vertical joints. With
    `stagger` the joints alternate (running bond), so only short vertical
    segments exist; without it they run through (stack bond)."""
    rng = np.random.default_rng(0)
    gray = cv2.GaussianBlur(rng.normal(150, 18, (H * 2, W * 2)).astype(np.float32), (0, 0), 3)
    img = cv2.cvtColor(np.clip(gray, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    course, joint = 70, 140
    for r, y in enumerate(range(40, H * 2, course)):
        cv2.line(img, (0, y), (W * 2, y), (60, 60, 60), 3)
        offset = joint // 2 if (stagger and r % 2) else 0
        for x in range(offset, W * 2, joint):
            cv2.line(img, (x, y), (x, y + course), (70, 70, 70), 3)
    return img


def _photo(wall: np.ndarray, yaw: float, pitch: float, focal_factor: float = 0.75) -> np.ndarray:
    f = focal_factor * LONG
    a, b = math.radians(yaw), math.radians(pitch)
    ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
    r = ry @ rx
    k = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]])
    th, tw = wall.shape[:2]
    to_center = np.array([[1, 0, -tw / 2], [0, 1, -th / 2], [0, 0, 1]])
    pose = np.column_stack([r[:, 0], r[:, 1], [0, 0, 1.6 * f]])
    out = cv2.warpPerspective(wall, k @ pose @ to_center, (W, H), borderMode=cv2.BORDER_REPLICATE)
    noise = np.random.default_rng(1).normal(0, 6, out.shape)
    return np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def _true_tilt(yaw: float, pitch: float) -> float:
    return math.degrees(math.acos(math.cos(math.radians(yaw)) * math.cos(math.radians(pitch))))


@pytest.fixture(scope="module")
def stack_bond():
    return _wall(stagger=False)


@pytest.fixture(scope="module")
def running_bond():
    return _wall(stagger=True)


def test_facing_wall_is_frontal(stack_bond):
    est = estimate_tilt(_photo(stack_bond, 0, 0))
    assert est.status == FRONTAL and not est.partial
    assert est.angle_deg < 3


@pytest.mark.parametrize("yaw,pitch", [(10, 10), (20, 15), (30, 20)])
def test_tilt_is_close_to_the_true_angle_when_the_assumed_lens_is_right(stack_bond, yaw, pitch):
    est = estimate_tilt(_photo(stack_bond, yaw, pitch))
    assert not est.partial
    assert abs(est.angle_deg - _true_tilt(yaw, pitch)) < 4


def test_strong_tilt_is_flagged(stack_bond):
    est = estimate_tilt(_photo(stack_bond, 30, 20))
    assert est.status == STRONG and est.angle_deg >= 20
    assert "إعادة التصوير" in est.note_ar


def test_one_direction_only_is_never_called_frontal(running_bond):
    # A running bond has no long vertical lines, so a photo taken looking up
    # (pitch 30) looks fine to the horizontal lines. It must not be reassuring.
    est = estimate_tilt(_photo(running_bond, 0, 30))
    assert est.partial and est.status == PARTIAL
    assert est.status != FRONTAL and est.vertical_deg is None
    assert "الاتجاه الآخر" in est.note_ar


def test_partial_measurement_above_the_limit_is_still_strong(running_bond):
    est = estimate_tilt(_photo(running_bond, 35, 0))
    assert est.partial and est.status == STRONG
    assert "أكبر" in est.note_ar


def test_wall_without_straight_lines_is_unmeasurable_not_guessed():
    rng = np.random.default_rng(5)
    blob = cv2.GaussianBlur(rng.normal(140, 25, (H, W)).astype(np.float32), (0, 0), 2)
    img = cv2.cvtColor(np.clip(blob, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    est = estimate_tilt(img)
    assert est.status == UNMEASURABLE and est.angle_deg is None


def test_same_photo_gives_the_same_answer(stack_bond):
    img = _photo(stack_bond, 20, 15)
    assert estimate_tilt(img).to_dict() == estimate_tilt(img).to_dict()


def test_assumed_lens_changes_the_estimate_as_documented(stack_bond):
    # The focal length is assumed, which is the main source of error: a longer
    # assumed lens reads the same photo as more tilted.
    img = _photo(stack_bond, 20, 0)
    assert estimate_tilt(img, focal_factor=0.5).angle_deg < estimate_tilt(img, focal_factor=1.0).angle_deg


def test_thresholds_come_from_the_arguments(stack_bond):
    img = _photo(stack_bond, 20, 0)
    assert estimate_tilt(img, warn_deg=40).status != STRONG
    assert estimate_tilt(img, warn_deg=10).status == STRONG


# ------------------------------------------------- quality check and the API
def test_quality_check_warns_about_tilt_but_never_rejects(stack_bond):
    pytest.importorskip("pydantic_settings")
    from app.vision.quality import assess_quality

    report = assess_quality(_photo(stack_bond, 30, 20))
    assert report.acceptable and not report.issues
    assert report.tilt["status"] == STRONG
    assert report.tilt["note_ar"] in report.warnings
    assert not any("لا يقيس النظام زاوية" in w for w in report.warnings)  # old static line is gone


def test_api_returns_tilt_for_accepted_images_and_none_for_rejected(client, samples):
    wall = client.post("/api/walls", json={"code": "W-TILT"}, headers=USER).json()

    def upload(name):
        path = samples / name
        with open(path, "rb") as f:
            r = client.post("/api/inspections", data={"wall_id": wall["id"]}, files={"image": (name, f, "image/jpeg")}, headers=USER)
        assert r.status_code == 201, r.text
        return r.json()

    ok = upload("synthetic_wall_T1.jpg")
    assert ok["status"] == "in_review"
    tilt = ok["quality"]["tilt"]
    assert tilt["status"] in {"frontal", "slight", "strong", "partial", "unmeasurable"}
    assert tilt["note_ar"]

    blurry = upload("synthetic_blurry.jpg")
    assert blurry["status"] == "rejected_quality" and blurry["quality"]["tilt"] is None
