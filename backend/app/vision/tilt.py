"""Rough camera-tilt estimate from a single wall photo.

This is an ESTIMATE, not a measurement. It looks for long straight lines (wall
edges, courses, joints), finds where each family of lines converges (a vanishing
point) and turns that into the angle between the wall plane and the image
plane. Two things limit it:

* the camera focal length is unknown, so a typical phone value is assumed
  (`focal_factor` x the long side of the image);
* mud walls often have few clean straight lines, so many photos come back as
  "unmeasurable". That answer is returned instead of a guess.

The thresholds are demo starting values. The acceptable tilt has to be set by a
restoration specialist; nothing here rejects an image.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import cv2
import numpy as np

FRONTAL = "frontal"
SLIGHT = "slight"
STRONG = "strong"
PARTIAL = "partial"  # one direction measured, small angle: no reassurance possible
UNMEASURABLE = "unmeasurable"

_WORK_SIZE = 1024  # long side used for line detection
_MIN_LINES = 6  # per family
_MIN_INLIER_FRACTION = 0.5  # share of the family's line length that must agree
_INLIER_SIN = math.sin(math.radians(1.5))  # direction tolerance for a line
_RANSAC_ROUNDS = 300


@dataclass
class TiltEstimate:
    status: str  # frontal | slight | strong | partial | unmeasurable
    angle_deg: float | None  # rough, uncalibrated
    horizontal_deg: float | None  # tilt seen by the roughly horizontal lines
    vertical_deg: float | None  # tilt seen by the roughly vertical lines
    lines_horizontal: int
    lines_vertical: int
    partial: bool  # only one direction could be measured
    note_ar: str

    def to_dict(self) -> dict:
        return asdict(self)


def _segments(gray: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    med = float(np.median(blurred))
    edges = cv2.Canny(blurred, max(0.0, 0.66 * med), min(255.0, 1.33 * med + 10))
    long_side = max(gray.shape)
    found = cv2.HoughLinesP(
        edges, 1, math.pi / 180, threshold=50, minLineLength=int(0.05 * long_side), maxLineGap=8
    )
    return np.empty((0, 4)) if found is None else found.reshape(-1, 4).astype(float)


def _family_tilt(segs: np.ndarray, center: tuple[float, float], focal: float) -> tuple[float, int] | None:
    """Angle (degrees) between this line family and the image plane, from the
    vanishing point most of the lines agree on. None when they do not agree."""
    if len(segs) < _MIN_LINES:
        return None
    cx, cy = center
    p1 = np.column_stack([segs[:, 0] - cx, segs[:, 1] - cy, np.ones(len(segs))])
    p2 = np.column_stack([segs[:, 2] - cx, segs[:, 3] - cy, np.ones(len(segs))])
    lines = np.cross(p1, p2)
    lines /= np.maximum(np.hypot(lines[:, 0], lines[:, 1]), 1e-9)[:, None]
    length = np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1])
    mid = (p1[:, :2] + p2[:, :2]) / 2
    unit = (p2[:, :2] - p1[:, :2]) / np.maximum(length, 1e-9)[:, None]

    def inliers(v: np.ndarray) -> np.ndarray:
        # Direction from each segment midpoint to the vanishing point; works for
        # a point at infinity too (v[2] == 0).
        target = v[:2][None, :] - mid * v[2]
        norm = np.maximum(np.hypot(target[:, 0], target[:, 1]), 1e-12)
        cross = np.abs(unit[:, 0] * target[:, 1] - unit[:, 1] * target[:, 0]) / norm
        return cross < _INLIER_SIN

    rng = np.random.default_rng(0)  # same photo, same answer
    prob = length / length.sum()
    best_v, best_score = None, 0.0
    for _ in range(_RANSAC_ROUNDS):
        i, j = rng.choice(len(segs), size=2, replace=False, p=prob)
        v = np.cross(lines[i], lines[j])
        n = np.linalg.norm(v)
        if n < 1e-9:
            continue
        v = v / n
        score = float(length[inliers(v)].sum())
        if score > best_score:
            best_v, best_score = v, score
    if best_v is None:
        return None

    mask = inliers(best_v)
    if mask.sum() < _MIN_LINES - 1 or length[mask].sum() / length.sum() < _MIN_INLIER_FRACTION:
        return None
    # Refine on the inliers: least-squares vanishing point (smallest singular vector).
    weighted = lines[mask] * length[mask][:, None]
    v = np.linalg.svd(weighted, full_matrices=False)[2][-1]
    angle = math.degrees(math.atan2(focal * abs(v[2]), math.hypot(v[0], v[1])))
    return angle, int(mask.sum())


def estimate_tilt(
    img: np.ndarray,
    *,
    focal_factor: float = 0.75,
    frontal_deg: float = 8.0,
    warn_deg: float = 20.0,
) -> TiltEstimate:
    h, w = img.shape[:2]
    scale = _WORK_SIZE / max(h, w)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    if scale < 1:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gh, gw = gray.shape[:2]
    focal = focal_factor * max(gh, gw)
    center = (gw / 2, gh / 2)

    segs = _segments(gray)
    horizontal = vertical = np.empty((0, 4))
    if len(segs):
        angle = np.degrees(np.arctan2(segs[:, 3] - segs[:, 1], segs[:, 2] - segs[:, 0]))
        angle = (angle + 90) % 180 - 90  # (-90, 90]
        horizontal = segs[np.abs(angle) <= 40]
        vertical = segs[np.abs(angle) >= 50]

    h_res = _family_tilt(horizontal, center, focal)
    v_res = _family_tilt(vertical, center, focal)
    h_deg = None if h_res is None else round(h_res[0], 1)
    v_deg = None if v_res is None else round(v_res[0], 1)

    if h_res is None and v_res is None:
        return TiltEstimate(
            UNMEASURABLE, None, None, None, len(horizontal), len(vertical), False,
            "تعذّر قياس زاوية التصوير آليًا (لا توجد خطوط مستقيمة كافية). صوّر الجدار بشكل عمودي قدر الإمكان.",
        )

    if h_res is not None and v_res is not None:
        total = math.degrees(math.acos(min(1.0, math.cos(math.radians(h_res[0])) * math.cos(math.radians(v_res[0])))))
        partial = False
    else:
        total = (h_res or v_res)[0]
        partial = True
    total = round(total, 1)

    if partial:
        # One direction only: a small angle proves nothing about the other one
        # (for example a photo taken looking up), so it is never called "frontal".
        which = "الأفقية" if h_res is not None else "الرأسية"
        if total >= warn_deg:
            status = STRONG
            text = (
                "الصورة مائلة كثيرًا عن مواجهة الجدار، وقد تتشوه أشكال التلف ومساحاتها. الأفضل إعادة التصوير من المواجهة. "
                f"الميل المقيس من الخطوط {which} فقط نحو {total:.0f}° (تقريبي)، وقد يكون الميل الفعلي أكبر."
            )
        else:
            status = PARTIAL
            text = (
                f"قُيس الميل من الخطوط {which} فقط (نحو {total:.0f}°، تقريبي)، ولا يمكن الجزم بالميل في الاتجاه الآخر "
                "(مثل التصوير من الأسفل للأعلى). صوّر الجدار بشكل عمودي قدر الإمكان."
            )
    else:
        if total < frontal_deg:
            status, text = FRONTAL, "الصورة مواجهة للجدار تقريبًا."
        elif total < warn_deg:
            status, text = SLIGHT, "الصورة مائلة قليلًا عن مواجهة الجدار."
        else:
            status = STRONG
            text = "الصورة مائلة كثيرًا عن مواجهة الجدار، وقد تتشوه أشكال التلف ومساحاتها. الأفضل إعادة التصوير من المواجهة."
        text += f" الميل التقديري نحو {total:.0f}° (تقريبي، يفترض عدسة هاتف نموذجية)."
    return TiltEstimate(status, total, h_deg, v_deg, len(horizontal), len(vertical), partial, text)
