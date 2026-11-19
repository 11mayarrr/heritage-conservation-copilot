"""Image registration between two photos of the same wall.

ORB features + RANSAC homography, on illumination-normalized (CLAHE) gray
images. If too few reliable matches are found, the result says so and the
comparison is marked unreliable instead of silently comparing misaligned
images."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.vision.imageio import resize_max

WORK_SIDE = 1400


@dataclass
class RegistrationResult:
    ok: bool
    homography: np.ndarray | None  # maps AFTER normalized coords -> BEFORE normalized coords
    matches: int
    inliers: int
    inlier_ratio: float
    message_ar: str


def normalize_illumination(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)


def _norm_matrix(w: int, h: int) -> np.ndarray:
    return np.array([[1 / w, 0, 0], [0, 1 / h, 0], [0, 0, 1]], dtype=np.float64)


def register(before: np.ndarray, after: np.ndarray) -> RegistrationResult:
    b, _ = resize_max(before, WORK_SIDE)
    a, _ = resize_max(after, WORK_SIDE)
    gb, ga = normalize_illumination(b), normalize_illumination(a)

    orb = cv2.ORB_create(nfeatures=5000)
    kb, db = orb.detectAndCompute(gb, None)
    ka, da = orb.detectAndCompute(ga, None)
    if db is None or da is None or len(kb) < 10 or len(ka) < 10:
        return RegistrationResult(False, None, 0, 0, 0.0, "لم تُعثر على نقاط مميزة كافية لمحاذاة الصورتين.")

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw = matcher.knnMatch(da, db, k=2)
    good = [m for m, n in (p for p in raw if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 12:
        return RegistrationResult(False, None, len(good), 0, 0.0,
                                  "التطابق بين الصورتين ضعيف. صوّر الجدار من زاوية ومسافة مقاربتين للصورة السابقة.")

    src = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if H is None:
        return RegistrationResult(False, None, len(good), 0, 0.0, "تعذر حساب تحويل المحاذاة.")
    inliers = int(mask.sum())
    ratio = inliers / len(good)
    # Express H in normalized coordinates so it works on polygons of any resolution.
    Hn = _norm_matrix(gb.shape[1], gb.shape[0]) @ H @ np.linalg.inv(_norm_matrix(ga.shape[1], ga.shape[0]))
    ok = inliers >= 15 and ratio >= 0.25
    msg = (
        f"تمت المحاذاة ({inliers} نقطة متطابقة موثوقة)."
        if ok
        else "المحاذاة غير موثوقة؛ نتائج المقارنة تحتاج مراجعة يدوية."
    )
    return RegistrationResult(ok, Hn, len(good), inliers, round(ratio, 3), msg)


def warp_polygon(poly: list[list[float]], Hn: np.ndarray) -> list[list[float]]:
    pts = np.array(poly, dtype=np.float64).reshape(-1, 1, 2)
    out = cv2.perspectiveTransform(pts, Hn).reshape(-1, 2)
    return [[float(min(1, max(0, x))), float(min(1, max(0, y)))] for x, y in out]


def warp_image(after: np.ndarray, before_shape: tuple[int, int], Hn: np.ndarray) -> np.ndarray:
    bh, bw = before_shape
    ah, aw = after.shape[:2]
    H = np.linalg.inv(_norm_matrix(bw, bh)) @ Hn @ _norm_matrix(aw, ah)
    return cv2.warpPerspective(after, H, (bw, bh))
