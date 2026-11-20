"""Pixel classifier trained on SYNTHETIC labeled images (scikit-learn).

Honest scope: it learns to separate the five damage styles that
`vision/synthetic.py` draws. It was never shown a real wall, so it will not
transfer to At-Turaif photos. It exists to prove the train / evaluate / plug-in
path end to end (scripts/train_synthetic.py, scripts/eval_synthetic.py) and to
be replaced by a model trained on expert-approved real annotations.

Output is tagged `model_synthetic_only` and never reported as validated.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.models.enums import ConfidenceSource
from app.vision.detectors.base import Detection, DetectorInfo
from app.vision.geometry import mask_to_polygons
from app.vision.imageio import resize_max
from app.vision.synthetic import LABEL_TO_DAMAGE

DEFAULT_WEIGHTS = Path(__file__).parent / "weights" / "synthetic_pixel_hgb.joblib"
WORK_SIDE = 640
FEAT_SCALE = 0.5  # features at half resolution for speed
MAX_CONF = 0.69


def extract_features(img: np.ndarray) -> np.ndarray:
    """Per-pixel features at FEAT_SCALE. Returns (h*w, F) float32 plus nothing else."""
    small = cv2.resize(img, None, fx=FEAT_SCALE, fy=FEAT_SCALE, interpolation=cv2.INTER_AREA)
    h, w = small.shape[:2]
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    gray = lab[..., 0]
    feats = [lab[..., 0], lab[..., 1], lab[..., 2], small[..., 0].astype(np.float32),
             small[..., 2].astype(np.float32) - small[..., 0].astype(np.float32)]
    for s in (1.5, 4, 10):
        g = cv2.GaussianBlur(gray, (0, 0), s)
        feats += [g, gray - g]
        sq = cv2.GaussianBlur(gray * gray, (0, 0), s)
        feats.append(np.sqrt(np.maximum(sq - g * g, 0)))
    for k in (5, 11):
        el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        feats += [cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, el), cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, el)]
    gx, gy = cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    feats.append(cv2.GaussianBlur(np.hypot(gx, gy), (0, 0), 2))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    feats += [yy / h, np.minimum(np.minimum(xx, w - 1 - xx), yy) / max(h, w)]
    for c in range(3):  # image-level context: pixel vs. global median
        feats.append(lab[..., c] - float(np.median(lab[..., c])))
    return np.stack(feats, -1).reshape(-1, len(feats)).astype(np.float32)


class SyntheticPixelDetector:
    info = DetectorInfo(
        name="synthetic-pixel-hgb",
        kind="model",
        version="0.1.0",
        validated=False,
        disclaimer=(
            "نموذج تصنيف بكسلات مدرّب على صور اصطناعية مرسومة بالكود فقط، ولم يرَ جدارًا حقيقيًا. "
            "يُستخدم لإثبات مسار التدريب والتقييم، ولا يصلح لتقدير تلف جدران الطريف. "
            "درجات الثقة غير معايرة."
        ),
    )

    def __init__(self, weights: str | Path | None = None):
        import joblib

        path = Path(weights) if weights else DEFAULT_WEIGHTS
        if not path.exists():
            raise RuntimeError(f"{path} not found. Run: python scripts/train_synthetic.py")
        self.clf = joblib.load(path)

    def predict_labels(self, img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return (label map at feature resolution, max-probability map)."""
        h, w = int(img.shape[0] * FEAT_SCALE), int(img.shape[1] * FEAT_SCALE)
        proba = self.clf.predict_proba(extract_features(img))
        classes = self.clf.classes_
        idx = proba.argmax(1)
        return classes[idx].reshape(h, w), proba.max(1).reshape(h, w)

    def detect(self, img: np.ndarray) -> list[Detection]:
        work, _ = resize_max(img, WORK_SIDE)
        labels, conf = self.predict_labels(work)
        out: list[Detection] = []
        for cid, dtype in LABEL_TO_DAMAGE.items():
            m = (labels == cid).astype(np.uint8)
            if not m.any():
                continue
            if cid == 1:
                # Thin cracks: bridge small gaps instead of opening them away.
                m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
                m = cv2.dilate(m, np.ones((3, 3), np.uint8))  # draw cracks with a visible outline
            else:
                m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
                m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
            min_area = 25 if cid == 1 else 60
            n, comp = cv2.connectedComponents(m)
            for k in range(1, n):
                cm = (comp == k).astype(np.uint8)
                if cm.sum() < min_area:
                    continue
                for poly in mask_to_polygons(cm, min_area_px=min_area):
                    score = min(float(conf[cm > 0].mean()), MAX_CONF)
                    out.append(
                        Detection(
                            damage_type=dtype,
                            polygon=poly,
                            confidence=round(score, 2),
                            confidence_source=ConfidenceSource.MODEL_SYNTHETIC,
                            description="ناتج نموذج مدرّب على بيانات اصطناعية فقط (غير مُتحقق).",
                        )
                    )
        return out
