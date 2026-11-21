"""SAM 2 adapter (Meta's Segment Anything Model 2), for click-to-segment.

Optional: needs PyTorch, the `sam2` package and a checkpoint, which are not
installed by default (see requirements-sam2.txt and scripts/download_sam2.py).

Configure with either:
  HCC_SAM2_CHECKPOINT=/path/sam2.1_hiera_tiny.pt  HCC_SAM2_CONFIG=configs/sam2.1/sam2.1_hiera_t.yaml
or
  HCC_SAM2_MODEL_ID=facebook/sam2.1-hiera-tiny     (downloads from Hugging Face on first use)

Note: this adapter follows the public `SAM2ImagePredictor` API; in this
repository it is tested with a stand-in predictor because the real weights
could not be downloaded in the development environment.
"""
from __future__ import annotations

import threading

import cv2
import numpy as np

from app.config import get_settings
from app.vision.segmenters.base import SegmenterInfo, SegmenterUnavailable, SegmentResult


def _build_predictor():
    s = get_settings()
    try:
        import torch
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except ImportError as e:
        raise SegmenterUnavailable("SAM 2 غير مثبت (pip install -r requirements-sam2.txt).") from e
    device = s.sam2_device or ("cuda" if torch.cuda.is_available() else "cpu")
    if s.sam2_checkpoint:
        from sam2.build_sam import build_sam2

        model = build_sam2(s.sam2_config, s.sam2_checkpoint, device=device)
        return SAM2ImagePredictor(model)
    if s.sam2_model_id:
        return SAM2ImagePredictor.from_pretrained(s.sam2_model_id, device=device)
    raise SegmenterUnavailable("حدد HCC_SAM2_CHECKPOINT أو HCC_SAM2_MODEL_ID لتفعيل SAM 2.")


class Sam2Segmenter:
    info = SegmenterInfo(
        name="sam2",
        kind="sam2",
        description_ar=(
            "تحديد الحدود بنموذج SAM 2. النموذج يرسم الحدود فقط ولا يحدد نوع التلف، "
            "ودرجته الداخلية ليست درجة ثقة معايرة للتلف."
        ),
    )

    def __init__(self, predictor=None):
        self._predictor = predictor or _build_predictor()
        self._cached_key: str | None = None
        self._lock = threading.Lock()  # the predictor holds one image embedding at a time

    def segment(self, img, points, box=None, cache_key=None) -> SegmentResult:
        h, w = img.shape[:2]
        with self._lock:
            if cache_key is None or cache_key != self._cached_key:
                self._predictor.set_image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                self._cached_key = cache_key
            kwargs: dict = {"multimask_output": True}
            if points:
                kwargs["point_coords"] = np.array([[x * w, y * h] for x, y, _ in points], dtype=np.float32)
                kwargs["point_labels"] = np.array([int(lab) for _, _, lab in points], dtype=np.int32)
            if box is not None:
                kwargs["box"] = np.array([box[0] * w, box[1] * h, box[2] * w, box[3] * h], dtype=np.float32)
            masks, scores, _ = self._predictor.predict(**kwargs)
        masks = np.asarray(masks)
        scores = np.asarray(scores).reshape(-1)
        best = int(np.argmax(scores))
        mask = (masks[best] > 0.5).astype(np.uint8) if masks.dtype != bool else masks[best].astype(np.uint8)
        return SegmentResult(mask=mask, score=round(float(scores[best]), 3), info=self.info,
                             extra={"candidates": len(scores)})
