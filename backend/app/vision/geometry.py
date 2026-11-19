"""Polygon helpers on normalized coordinates (0..1)."""
from __future__ import annotations

import cv2
import numpy as np

Polygon = list[list[float]]


def polygon_area(poly: Polygon) -> float:
    if len(poly) < 3:
        return 0.0
    a = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


def clamp_polygon(poly: Polygon) -> Polygon:
    return [[min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y)))] for x, y in poly]


def validate_polygon(poly: Polygon) -> Polygon:
    if not isinstance(poly, list) or len(poly) < 3:
        raise ValueError("المضلع يحتاج ثلاث نقاط على الأقل.")
    for p in poly:
        if not (isinstance(p, (list, tuple)) and len(p) == 2):
            raise ValueError("كل نقطة يجب أن تكون [x, y].")
    return clamp_polygon(poly)


def centroid(poly: Polygon) -> tuple[float, float]:
    xs, ys = zip(*poly)
    return sum(xs) / len(xs), sum(ys) / len(ys)


def column_label(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def grid_cells(poly: Polygon, cols: int, rows: int) -> list[str]:
    """Reference-grid cells (e.g. 'B3') that the polygon overlaps.
    Columns are lettered left->right, rows numbered top->bottom."""
    mask = polygon_mask(poly, cols * 20, rows * 20)
    cells = []
    for r in range(rows):
        for c in range(cols):
            if mask[r * 20 : (r + 1) * 20, c * 20 : (c + 1) * 20].any():
                cells.append(f"{column_label(c)}{r + 1}")
    if not cells:
        cx, cy = centroid(poly)
        cells.append(f"{column_label(min(cols - 1, int(cx * cols)))}{min(rows, int(cy * rows) + 1)}")
    return cells


def polygon_mask(poly: Polygon, width: int, height: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    pts = np.array([[x * width, y * height] for x, y in poly], dtype=np.int32)
    cv2.fillPoly(mask, [pts], 1)
    return mask


def mask_to_polygons(mask: np.ndarray, min_area_px: int = 30, epsilon_frac: float = 0.004) -> list[Polygon]:
    h, w = mask.shape[:2]
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in contours:
        if cv2.contourArea(c) < min_area_px:
            continue
        eps = epsilon_frac * cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        if len(approx) < 3:
            continue
        out.append([[float(x) / w, float(y) / h] for x, y in approx])
    return out


def iou(a: Polygon, b: Polygon, res: int = 512) -> float:
    ma, mb = polygon_mask(a, res, res), polygon_mask(b, res, res)
    inter = np.logical_and(ma, mb).sum()
    union = np.logical_or(ma, mb).sum()
    return float(inter / union) if union else 0.0
