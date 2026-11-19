"""Fallback promptable segmenter using OpenCV GrabCut.

Works with no model download. Much less accurate than SAM 2 on complex
textures such as mud plaster: it separates regions by color statistics, so it
works best when the damaged area looks clearly different from its surroundings.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.vision.imageio import resize_max
from app.vision.segmenters.base import SegmenterInfo, SegmentResult

WORK_SIDE = 900


class GrabCutSegmenter:
    info = SegmenterInfo(
        name="opencv-grabcut",
        kind="grabcut",
        description_ar=(
            "تحديد تقريبي بخوارزمية GrabCut (بديل يعمل دون تنزيل نموذج). دقته أقل من SAM 2 على "
            "أسطح الطين المتجانسة؛ راجع الحدود قبل الحفظ."
        ),
    )

    def segment(self, img, points, box=None, cache_key=None) -> SegmentResult:
        h0, w0 = img.shape[:2]
        work, _ = resize_max(img, WORK_SIDE)
        h, w = work.shape[:2]
        diag = float(np.hypot(h, w))
        pos = [(int(x * w), int(y * h)) for x, y, lab in points if lab == 1]
        neg = [(int(x * w), int(y * h)) for x, y, lab in points if lab == 0]

        if box is not None:
            x0, y0, x1, y1 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
        else:
            # No box: search a window around the positive points.
            r = int(0.12 * diag)
            xs, ys = [p[0] for p in pos], [p[1] for p in pos]
            x0, y0 = max(0, min(xs) - r), max(0, min(ys) - r)
            x1, y1 = min(w - 1, max(xs) + r), min(h - 1, max(ys) + r)

        mask = np.full((h, w), cv2.GC_BGD, np.uint8)
        mask[y0:y1, x0:x1] = cv2.GC_PR_BGD
        # Pixels similar in color to the clicked points start as "probably region".
        lab = cv2.cvtColor(cv2.GaussianBlur(work, (5, 5), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
        if pos:
            seeds = np.array([lab[y, x] for x, y in pos])
            dist = np.min(np.linalg.norm(lab[..., None, :] - seeds[None, None], axis=-1), axis=-1)
            similar = (dist < 18) & (mask == cv2.GC_PR_BGD)
            mask[similar] = cv2.GC_PR_FGD
        rad = max(3, int(0.012 * diag))
        for x, y in pos:
            cv2.circle(mask, (x, y), rad, cv2.GC_FGD, -1)
        for x, y in neg:
            cv2.circle(mask, (x, y), rad, cv2.GC_BGD, -1)

        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(work, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
        except cv2.error:
            pass  # degenerate prompts: fall back to the seeded mask below
        out = np.isin(mask, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
        out = cv2.morphologyEx(out, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        out = _keep_components_with_points(out, pos)
        out = cv2.resize(out, (w0, h0), interpolation=cv2.INTER_NEAREST)
        return SegmentResult(mask=out, score=None, info=self.info)


def _keep_components_with_points(mask: np.ndarray, pos: list[tuple[int, int]]) -> np.ndarray:
    """Drop blobs the expert did not click on."""
    if not pos:
        return mask
    n, labels = cv2.connectedComponents(mask)
    keep = {labels[y, x] for x, y in pos if labels[y, x] > 0}
    return np.isin(labels, list(keep)).astype(np.uint8) if keep else mask
