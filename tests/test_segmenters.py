import cv2
import numpy as np
import pytest

from app.vision.segmenters import validate_prompts
from app.vision.segmenters.grabcut import GrabCutSegmenter
from app.vision.segmenters.sam2_adapter import Sam2Segmenter
from make_synthetic_samples import mud_texture


@pytest.fixture(scope="module")
def blob_image():
    img = mud_texture(1200, 900, 3)
    blob = np.zeros(img.shape[:2], np.uint8)
    cv2.ellipse(blob, (700, 400), (150, 90), 20, 0, 360, 1, -1)
    img[blob > 0] = (img[blob > 0] * 0.45).astype(np.uint8)
    return img, blob


def _iou(a, b):
    return (a & b).sum() / (a | b).sum()


def test_grabcut_outlines_clicked_area(blob_image):
    img, blob = blob_image
    res = GrabCutSegmenter().segment(img, [[700 / 1200, 400 / 900, 1]])
    assert res.mask.shape == blob.shape
    assert _iou(res.mask, blob) > 0.8
    assert res.score is None  # no fake confidence


def test_grabcut_negative_point_and_box(blob_image):
    img, blob = blob_image
    res = GrabCutSegmenter().segment(img, [[700 / 1200, 400 / 900, 1], [0.1, 0.1, 0]], box=[0.4, 0.25, 0.8, 0.7])
    assert _iou(res.mask, blob) > 0.8


@pytest.mark.parametrize("points,box", [([], None), ([[0.5, 0.5, 0]], None), ([[1.5, 0.5, 1]], None),
                                        ([[0.5, 0.5, 1]], [0.6, 0.1, 0.2, 0.9])])
def test_invalid_prompts_rejected(points, box):
    with pytest.raises(ValueError):
        validate_prompts(points, box)


class FakePredictor:
    """Stand-in for sam2.SAM2ImagePredictor: records calls, returns 3 candidate masks."""

    def __init__(self):
        self.set_calls = 0
        self.last = None

    def set_image(self, rgb):
        assert rgb.ndim == 3 and rgb.dtype == np.uint8
        self.set_calls += 1
        self.shape = rgb.shape[:2]

    def predict(self, point_coords=None, point_labels=None, box=None, multimask_output=True):
        self.last = dict(point_coords=point_coords, point_labels=point_labels, box=box)
        h, w = self.shape
        masks = np.zeros((3, h, w), np.float32)
        masks[1, 10:20, 30:60] = 1.0
        return masks, np.array([0.2, 0.9, 0.5]), None


def test_sam2_adapter_converts_prompts_caches_embedding_and_picks_best():
    fake = FakePredictor()
    seg = Sam2Segmenter(predictor=fake)
    img = np.zeros((100, 200, 3), np.uint8)
    res = seg.segment(img, [[0.25, 0.5, 1], [0.75, 0.5, 0]], box=[0.1, 0.1, 0.5, 0.9], cache_key="a")
    np.testing.assert_allclose(fake.last["point_coords"], [[50, 50], [150, 50]])
    assert list(fake.last["point_labels"]) == [1, 0]
    np.testing.assert_allclose(fake.last["box"], [20, 10, 100, 90])
    assert res.score == 0.9 and res.mask[15, 40] == 1 and res.mask.sum() == 300
    seg.segment(img, [[0.3, 0.3, 1]], cache_key="a")
    assert fake.set_calls == 1  # same image: embedding reused
    seg.segment(img, [[0.3, 0.3, 1]], cache_key="b")
    assert fake.set_calls == 2


def test_segment_endpoint_returns_preview_without_saving(client, samples):
    w = client.post("/api/walls", json={"code": "W-S"}).json()
    with open(samples / "synthetic_wall_T1.jpg", "rb") as f:
        insp = client.post("/api/inspections", data={"wall_id": w["id"]}, files={"image": ("a.jpg", f, "image/jpeg")}).json()
    before = len(client.get(f"/api/audit?inspection_id={insp['id']}").json())
    # Click on the dark basal band of the synthetic wall.
    r = client.post(f"/api/inspections/{insp['id']}/segment", json={"points": [[0.4, 0.93, 1]]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["segmenter"]["kind"] in ("grabcut", "sam2")
    assert body["polygon"] and len(body["polygon"]) >= 3
    assert len(client.get(f"/api/audit?inspection_id={insp['id']}").json()) == before
    assert client.post(f"/api/inspections/{insp['id']}/segment", json={"points": []}).status_code == 422
    h = client.get("/api/health").json()
    assert h["segmenter"]["kind"] == "grabcut" and h["segmenter_fallback_reason"]
