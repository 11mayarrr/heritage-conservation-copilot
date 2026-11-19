"""Temporal change intelligence between two inspections of the same wall.

The comparison is done on DAMAGE REGIONS (after warping the newer regions into
the older photo's frame), not on raw pixels. Raw pixel differences are only
reported as low-confidence "visual change candidates", after illumination
normalization, because lighting, shadows and white balance change between
visits and must not be read as new damage.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.vision.geometry import iou, polygon_area, polygon_mask
from app.vision.registration import RegistrationResult, normalize_illumination, warp_image, warp_polygon

GROWTH_THRESHOLD = 0.15  # +15% area counts as "grew"
MATCH_IOU = 0.1


def compare_regions(before: list[dict], after: list[dict], reg: RegistrationResult) -> dict:
    """before/after: active region dicts (id, index, damage_type, polygon)."""
    if not reg.ok or reg.homography is None:
        warped = [dict(r, polygon_in_before=r["polygon"]) for r in after]
    else:
        warped = [dict(r, polygon_in_before=warp_polygon(r["polygon"], reg.homography)) for r in after]

    matched_before: set[str] = set()
    items = []
    for a in warped:
        best, best_iou = None, 0.0
        for b in before:
            v = iou(a["polygon_in_before"], b["polygon"])
            if v > best_iou:
                best, best_iou = b, v
        area_a = polygon_area(a["polygon_in_before"])
        if best is None or best_iou < MATCH_IOU:
            status = "new"
            label = "منطقة جديدة"
            growth = None
        else:
            matched_before.add(best["id"])
            area_b = polygon_area(best["polygon"])
            growth = (area_a - area_b) / area_b if area_b else None
            if growth is not None and growth > GROWTH_THRESHOLD:
                status, label = "grew", "زاد فيها التلف"
            else:
                status, label = "unchanged", "لم تتغير بشكل ملحوظ"
        items.append(
            {
                "after_region_id": a["id"],
                "after_index": a["index"],
                "before_region_id": best["id"] if best and best_iou >= MATCH_IOU else None,
                "before_index": best["index"] if best and best_iou >= MATCH_IOU else None,
                "damage_type": a["damage_type"],
                "status": status,
                "status_ar": label,
                "iou": round(best_iou, 3),
                "area_change": None if growth is None else round(growth, 3),
                "polygon_in_before": a["polygon_in_before"],
            }
        )
    for b in before:
        if b["id"] not in matched_before:
            items.append(
                {
                    "after_region_id": None,
                    "after_index": None,
                    "before_region_id": b["id"],
                    "before_index": b["index"],
                    "damage_type": b["damage_type"],
                    "status": "not_found",
                    "status_ar": "غير ظاهرة في الصورة الأحدث (قد تكون رُممت أو حُجبت، تحقق ميدانيًا)",
                    "iou": 0.0,
                    "area_change": None,
                    "polygon_in_before": b["polygon"],
                }
            )
    summary = {s: sum(1 for i in items if i["status"] == s) for s in ("new", "grew", "unchanged", "not_found")}
    return {"items": items, "summary": summary, "reliable": reg.ok}


def visual_change_candidates(before: np.ndarray, after: np.ndarray, reg: RegistrationResult) -> dict:
    """Pixel-level change map after alignment and illumination normalization.
    Always low confidence; shown in gray as 'candidates for review'."""
    if not reg.ok or reg.homography is None:
        return {"available": False, "reason_ar": "لا تتوفر خريطة تغير بصري لأن المحاذاة غير موثوقة.", "candidates": []}
    h, w = before.shape[:2]
    scale = min(1.0, 1200 / max(h, w))
    size = (int(w * scale), int(h * scale))
    b = cv2.resize(before, size)
    a = cv2.resize(warp_image(after, (h, w), reg.homography), size)
    valid = cv2.resize((cv2.cvtColor(warp_image(after, (h, w), reg.homography), cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8), size)
    nb, na = normalize_illumination(b).astype(np.float32), normalize_illumination(a).astype(np.float32)
    # Remove global brightness/contrast differences.
    na = (na - na[valid > 0].mean()) / (na[valid > 0].std() + 1e-6) * nb.std() + nb.mean()
    diff = np.abs(cv2.GaussianBlur(nb, (0, 0), 3) - cv2.GaussianBlur(na, (0, 0), 3))
    diff[valid == 0] = 0
    thr = max(35.0, float(np.percentile(diff[valid > 0], 99)))
    mask = cv2.morphologyEx((diff > thr).astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    from app.vision.geometry import mask_to_polygons

    polys = mask_to_polygons(mask, min_area_px=int(0.002 * size[0] * size[1]), epsilon_frac=0.01)
    return {
        "available": True,
        "reason_ar": "مناطق تغير بصري مرشحة بعد تطبيع الإضاءة. ثقتها منخفضة وقد تكون ظلالًا أو أشخاصًا أو اختلاف رطوبة سطحية.",
        "candidates": [{"polygon": p, "confidence": 0.3} for p in polys[:30]],
    }


def side_by_side(before: np.ndarray, after_aligned: np.ndarray) -> np.ndarray:
    h = min(before.shape[0], 900)
    def fit(img):
        s = h / img.shape[0]
        return cv2.resize(img, (int(img.shape[1] * s), h))
    gap = np.full((h, 12, 3), 255, dtype=np.uint8)
    return np.hstack([fit(before), gap, fit(after_aligned)])


def mask_union_fraction(regions: list[dict]) -> float:
    if not regions:
        return 0.0
    m = np.zeros((512, 512), dtype=np.uint8)
    for r in regions:
        m |= polygon_mask(r["polygon"], 512, 512)
    return float(m.mean())
