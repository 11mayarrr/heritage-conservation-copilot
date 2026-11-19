"""Promptable segmentation: the expert clicks on a region, the segmenter draws
its boundary. It never decides the damage type; the expert does.

Prompts use normalized coordinates (0..1):
  points: [[x, y, label], ...]  label 1 = inside the region, 0 = outside
  box:    [x0, y0, x1, y1] (optional)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass
class SegmenterInfo:
    name: str
    kind: str  # "sam2" | "grabcut"
    description_ar: str


@dataclass
class SegmentResult:
    mask: np.ndarray  # uint8 HxW, 1 = region
    score: float | None  # model's own score when it has one (not a calibrated confidence)
    info: SegmenterInfo
    extra: dict = field(default_factory=dict)


class PromptSegmenter(Protocol):
    info: SegmenterInfo

    def segment(
        self,
        img: np.ndarray,
        points: list[list[float]],
        box: list[float] | None = None,
        cache_key: str | None = None,
    ) -> SegmentResult: ...


class SegmenterUnavailable(RuntimeError):
    pass


def validate_prompts(points: list[list[float]], box: list[float] | None) -> None:
    if not points and box is None:
        raise ValueError("أضف نقطة واحدة على الأقل داخل المنطقة أو ارسم مستطيلًا.")
    for p in points:
        if len(p) != 3 or p[2] not in (0, 1) or not (0 <= p[0] <= 1 and 0 <= p[1] <= 1):
            raise ValueError("كل نقطة يجب أن تكون [x, y, 1 أو 0] بإحداثيات بين 0 و1.")
    if points and not any(p[2] == 1 for p in points) and box is None:
        raise ValueError("أضف نقطة واحدة على الأقل داخل المنطقة.")
    if box is not None:
        if len(box) != 4 or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
            raise ValueError("المستطيل غير صالح.")
