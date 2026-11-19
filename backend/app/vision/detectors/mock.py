"""Mock adapter: returns fixed, clearly-labeled demo regions so the full
workflow (atlas colors, review, report) can be shown without a trained model.

NEVER present these as real findings. Every region is tagged
confidence_source="mock" and the UI/report show a "بيانات وهمية" banner.
"""
from __future__ import annotations

import numpy as np

from app.models.enums import ConfidenceSource, DamageType
from app.vision.detectors.base import Detection, DetectorInfo

_DEMO = [
    (DamageType.CRACK, [[0.30, 0.18], [0.33, 0.18], [0.36, 0.45], [0.33, 0.46]], 0.62),
    (DamageType.PLASTER_LOSS, [[0.55, 0.25], [0.72, 0.22], [0.75, 0.40], [0.58, 0.43]], 0.55),
    (DamageType.MOISTURE_EROSION, [[0.05, 0.80], [0.60, 0.78], [0.62, 0.97], [0.04, 0.97]], 0.48),
    (DamageType.MATERIAL_LOSS, [[0.78, 0.60], [0.90, 0.58], [0.92, 0.75], [0.80, 0.78]], 0.51),
    (DamageType.EDGE_EROSION, [[0.93, 0.05], [0.99, 0.05], [0.99, 0.35], [0.94, 0.33]], 0.44),
    (DamageType.UNCERTAIN, [[0.12, 0.40], [0.22, 0.38], [0.24, 0.52], [0.13, 0.54]], 0.30),
]


class MockDetector:
    info = DetectorInfo(
        name="mock-adapter",
        kind="mock",
        version="0.1.0",
        validated=False,
        disclaimer=(
            "بيانات وهمية للعرض فقط: المناطق ثابتة ولا تعتمد على محتوى الصورة. "
            "استبدل هذا المحول بنموذج مدرب قبل أي استخدام فعلي."
        ),
    )

    def detect(self, img: np.ndarray) -> list[Detection]:
        return [
            Detection(
                damage_type=t,
                polygon=[list(p) for p in poly],
                confidence=c,
                confidence_source=ConfidenceSource.MOCK,
                description="منطقة تجريبية وهمية لعرض سير العمل، وليست نتيجة تحليل.",
            )
            for t, poly, c in _DEMO
        ]
