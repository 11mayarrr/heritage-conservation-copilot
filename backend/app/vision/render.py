"""Draw the unified damage atlas: fixed colors, reference grid, region labels
and a legend. Output is a PNG the expert can download or put in the report."""
from __future__ import annotations

import cv2
import numpy as np

from app.models.enums import DAMAGE_COLORS, DamageType, RegionStatus
from app.vision.geometry import column_label


def hex_to_bgr(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)


LEGEND_EN = {
    DamageType.CRACK: "Crack",
    DamageType.PLASTER_LOSS: "Plaster loss / flaking",
    DamageType.MOISTURE_EROSION: "Moisture erosion",
    DamageType.MATERIAL_LOSS: "Material loss / structural",
    DamageType.EDGE_EROSION: "Edge erosion (dashed)",
    DamageType.UNCERTAIN: "Uncertain / needs inspection",
}


def _dashed_polyline(img, pts, color, thickness, dash=12):
    for p0, p1 in zip(pts, np.roll(pts, -1, axis=0)):
        length = int(np.hypot(*(p1 - p0)))
        for s in range(0, length, dash * 2):
            a = p0 + (p1 - p0) * (s / max(1, length))
            b = p0 + (p1 - p0) * (min(length, s + dash) / max(1, length))
            cv2.line(img, tuple(a.astype(int)), tuple(b.astype(int)), color, thickness, cv2.LINE_AA)


def render_atlas(
    img: np.ndarray,
    regions: list[dict],
    grid: tuple[int, int] | None = None,
    legend: bool = True,
    fill_alpha: float = 0.35,
) -> np.ndarray:
    """regions: dicts with damage_type, polygon, index, status."""
    out = img.copy()
    h, w = out.shape[:2]
    thick = max(2, int(max(h, w) / 500))

    if grid:
        cols, rows = grid
        gcolor = (235, 235, 235)
        for c in range(1, cols):
            x = int(c * w / cols)
            cv2.line(out, (x, 0), (x, h), gcolor, 1, cv2.LINE_AA)
        for r in range(1, rows):
            y = int(r * h / rows)
            cv2.line(out, (0, y), (w, y), gcolor, 1, cv2.LINE_AA)
        fs = max(0.4, max(h, w) / 2200)
        for c in range(cols):
            for r in range(rows):
                cv2.putText(out, f"{column_label(c)}{r + 1}", (int(c * w / cols) + 4, int(r * h / rows) + int(18 * fs * 2)),
                            cv2.FONT_HERSHEY_SIMPLEX, fs, (250, 250, 250), 1, cv2.LINE_AA)

    overlay = out.copy()
    visible = [r for r in regions if r.get("status") != RegionStatus.REJECTED.value]
    for r in visible:
        color = hex_to_bgr(DAMAGE_COLORS[DamageType(r["damage_type"])])
        pts = np.array([[x * w, y * h] for x, y in r["polygon"]], dtype=np.int32)
        cv2.fillPoly(overlay, [pts], color)
    out = cv2.addWeighted(overlay, fill_alpha, out, 1 - fill_alpha, 0)

    for r in visible:
        dtype = DamageType(r["damage_type"])
        color = hex_to_bgr(DAMAGE_COLORS[dtype])
        pts = np.array([[x * w, y * h] for x, y in r["polygon"]], dtype=np.float64)
        if dtype == DamageType.EDGE_EROSION or dtype == DamageType.UNCERTAIN:
            _dashed_polyline(out, pts, color, thick)
        else:
            cv2.polylines(out, [pts.astype(np.int32)], True, color, thick, cv2.LINE_AA)
        label = f"R{r['index']}"
        x0, y0 = pts.min(axis=0).astype(int)
        fs = max(0.5, max(h, w) / 1800)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, fs, 2)
        y0 = max(th + 4, y0)
        cv2.rectangle(out, (x0, y0 - th - 6), (x0 + tw + 6, y0), color, -1)
        cv2.putText(out, label, (x0 + 3, y0 - 4), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), 2, cv2.LINE_AA)

    if legend:
        out = _add_legend(out)
    return out


def _add_legend(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    fs = max(0.45, w / 2400)
    row = int(34 * fs * 1.6)
    panel = np.full((row * 4 + 10, w, 3), 250, dtype=np.uint8)
    items = list(LEGEND_EN.items())
    per_col = 3
    col_w = w // 2
    for i, (dtype, text) in enumerate(items):
        cx = 12 + (i // per_col) * col_w
        cy = 10 + (i % per_col) * row
        cv2.rectangle(panel, (cx, cy), (cx + row - 8, cy + row - 8), hex_to_bgr(DAMAGE_COLORS[dtype]), -1)
        cv2.putText(panel, text, (cx + row + 4, cy + row - 14), cv2.FONT_HERSHEY_SIMPLEX, fs, (40, 40, 40), 1, cv2.LINE_AA)
    cv2.putText(panel, "Preliminary - requires conservator approval", (12, 10 + 3 * row + row // 2),
                cv2.FONT_HERSHEY_SIMPLEX, fs, (60, 60, 160), 1, cv2.LINE_AA)
    return np.vstack([img, panel])
