"""Integration point for a trained segmentation model (YOLO-seg, SegFormer...).

Not active in the MVP: no model trained on At-Turaif walls exists yet.
To plug one in:

1. Train on expert-annotated masks exported from the review UI
   (scripts/export_annotations.py writes COCO-style polygons).
2. Set HCC_DETECTOR=model and HCC_MODEL_WEIGHTS=/path/to/weights.
3. Map the model's class ids to DamageType in CLASS_MAP below.
4. Evaluate against held-out expert masks (scripts/evaluate.py) and only then
   set `validated=True`.

SAM 2 is a promptable segmenter, not a damage classifier: use it to refine the
boundary of a region the expert clicks on, not to decide the damage type.
"""
from __future__ import annotations

import os

import numpy as np

from app.models.enums import ConfidenceSource, DamageType
from app.vision.detectors.base import Detection, DetectorInfo
from app.vision.geometry import mask_to_polygons

CLASS_MAP: dict[int, DamageType] = {
    0: DamageType.CRACK,
    1: DamageType.PLASTER_LOSS,
    2: DamageType.MOISTURE_EROSION,
    3: DamageType.MATERIAL_LOSS,
    4: DamageType.EDGE_EROSION,
}


class YoloSegDetector:
    info = DetectorInfo(
        name="yolo-seg",
        kind="model",
        version="custom",
        validated=False,
        disclaimer="نموذج تقسيم مخصص لم يُقيّم بعد مقابل تعليقات المختصين.",
    )

    def __init__(self, weights: str | None = None, conf: float = 0.25):
        weights = weights or os.environ.get("HCC_MODEL_WEIGHTS")
        if not weights:
            raise RuntimeError("HCC_MODEL_WEIGHTS is not set; no trained model available.")
        try:
            from ultralytics import YOLO  # optional dependency
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("pip install ultralytics to use the YOLO detector") from e
        self.model = YOLO(weights)
        self.conf = conf

    def detect(self, img: np.ndarray) -> list[Detection]:  # pragma: no cover
        res = self.model.predict(img, conf=self.conf, verbose=False)[0]
        out: list[Detection] = []
        if res.masks is None:
            return out
        for mask, cls, score in zip(res.masks.data.cpu().numpy(), res.boxes.cls, res.boxes.conf):
            dtype = CLASS_MAP.get(int(cls), DamageType.UNCERTAIN)
            for poly in mask_to_polygons((mask > 0.5).astype(np.uint8)):
                out.append(
                    Detection(
                        damage_type=dtype,
                        polygon=poly,
                        confidence=round(float(score), 2),
                        confidence_source=ConfidenceSource.MODEL,
                        description="ناتج نموذج تقسيم مخصص (غير مُقيّم).",
                    )
                )
        return out
