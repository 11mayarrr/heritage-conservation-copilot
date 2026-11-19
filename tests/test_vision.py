import cv2
import numpy as np

from app.privacy.anonymizer import anonymize, apply_manual_boxes
from app.vision.detectors import get_detector
from app.vision.geometry import grid_cells, iou, polygon_area
from app.vision.quality import assess_quality
from app.vision.registration import register, warp_polygon


def test_quality_accepts_sharp_and_rejects_blurry_dark(samples):
    assert assess_quality(cv2.imread(str(samples / "synthetic_wall_T1.jpg"))).acceptable
    blurry = assess_quality(cv2.imread(str(samples / "synthetic_blurry.jpg")))
    assert not blurry.acceptable and any("واضحة" in i for i in blurry.issues)
    dark = assess_quality(cv2.imread(str(samples / "synthetic_dark.jpg")))
    assert not dark.acceptable and any("مظلمة" in i for i in dark.issues)


def test_quality_rejects_low_resolution():
    small = (np.random.default_rng(0).random((200, 300, 3)) * 255).astype(np.uint8)
    q = assess_quality(small)
    assert not q.acceptable and any("دقة" in i for i in q.issues)


def test_geometry_area_grid_iou():
    sq = [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]]
    assert abs(polygon_area(sq) - 0.25) < 1e-9
    assert grid_cells([[0.01, 0.01], [0.1, 0.01], [0.1, 0.1]], 6, 4) == ["A1"]
    assert "F4" in grid_cells([[0.9, 0.9], [0.99, 0.9], [0.99, 0.99]], 6, 4)
    assert iou(sq, sq) > 0.99
    assert iou(sq, [[0.6, 0.6], [0.9, 0.6], [0.9, 0.9]]) == 0


def test_heuristic_detects_synthetic_crack_with_uncalibrated_confidence(samples):
    img = cv2.imread(str(samples / "synthetic_wall_T1.jpg"))
    dets = get_detector("heuristic").detect(img)
    cracks = [d for d in dets if d.damage_type.value == "crack"]
    assert cracks, "expected the drawn crack to be found"
    for d in dets:
        assert d.confidence < 0.7  # heuristic scores are capped
        assert d.confidence_source.value == "heuristic_uncalibrated"
    # Dark areas are never given a cause.
    assert all(d.damage_type.value in ("crack", "uncertain") for d in dets)


def test_heuristic_on_plain_texture_finds_no_cracks():
    rng = np.random.default_rng(1)
    img = np.full((900, 1200, 3), (120, 160, 196), np.uint8)
    img = cv2.add(img, (rng.normal(0, 6, img.shape)).astype(np.int8), dtype=cv2.CV_8U)
    dets = get_detector("heuristic").detect(img)
    assert not [d for d in dets if d.damage_type.value == "crack"]


def test_mock_detector_is_labeled_mock(samples):
    img = cv2.imread(str(samples / "synthetic_wall_T1.jpg"))
    det = get_detector("mock")
    assert det.info.kind == "mock" and not det.info.validated
    assert {d.confidence_source.value for d in det.detect(img)} == {"mock"}


def test_anonymizer_keeps_wall_without_faces_and_blurs_manual_boxes(samples):
    img = cv2.imread(str(samples / "synthetic_wall_T1.jpg"))
    out, info = anonymize(img)
    assert info["faces_hidden"] == 0 and info["original_stored"] is False
    assert np.array_equal(out, img)
    blurred = apply_manual_boxes(img, [[0.1, 0.1, 0.2, 0.2]])
    h, w = img.shape[:2]
    roi = (slice(int(0.1 * h), int(0.3 * h)), slice(int(0.1 * w), int(0.3 * w)))
    assert blurred[roi].std() < img[roi].std()
    assert np.array_equal(blurred[int(0.6 * h):, :], img[int(0.6 * h):, :])


def test_registration_recovers_viewpoint_shift(samples):
    a = cv2.imread(str(samples / "synthetic_wall_T1.jpg"))
    b = cv2.imread(str(samples / "synthetic_wall_T2.jpg"))
    reg = register(a, b)
    assert reg.ok and reg.inliers >= 15
    # The image centre should map close to the centre (small shift/rotation only).
    cx, cy = warp_polygon([[0.5, 0.5]], reg.homography)[0]
    assert abs(cx - 0.5) < 0.05 and abs(cy - 0.5) < 0.05


def test_registration_fails_honestly_on_unrelated_images(samples):
    a = cv2.imread(str(samples / "synthetic_wall_T1.jpg"))
    rng = np.random.default_rng(3)
    noise = (rng.random(a.shape) * 255).astype(np.uint8)
    assert not register(a, noise).ok
