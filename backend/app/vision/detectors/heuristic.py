"""OpenCV heuristic detector (no training data required).

What it does:
  * Cracks: thin, dark, elongated structures found with a morphological
    black-hat filter on a contrast-normalized image.
  * Dark anomalies: areas clearly darker than their surroundings. These may be
    moisture staining, but also shadows, openings, decoration or old repairs,
    so they are always labeled UNCERTAIN, never given a cause.

What it does NOT do: classify plaster loss, material loss or edge erosion.
Those need a trained segmentation model or the expert (manual regions).

Confidence numbers are uncalibrated heuristic scores, capped below 0.7, and are
tagged `heuristic_uncalibrated` everywhere they are shown.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.models.enums import ConfidenceSource, DamageType
from app.vision.detectors.base import Detection, DetectorInfo
from app.vision.geometry import mask_to_polygons
from app.vision.imageio import resize_max

WORK_SIDE = 1280
MAX_CONF = 0.69


class HeuristicDetector:
    info = DetectorInfo(
        name="opencv-heuristic",
        kind="heuristic",
        version="0.1.0",
        validated=False,
        disclaimer=(
            "كاشف تجريبي يعتمد على قواعد معالجة صور (OpenCV) وليس نموذجًا مدربًا على "
            "جدران الطريف. درجات الثقة تقديرية غير معايرة، وقد يخلط بين التشققات "
            "والفواصل أو الزخارف أو الظلال. لم تُقس دقته بعد."
        ),
    )

    def detect(self, img: np.ndarray) -> list[Detection]:
        work, _ = resize_max(img, WORK_SIDE)
        gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        norm = clahe.apply(gray)
        return self._cracks(norm) + self._dark_anomalies(norm)

    # ------------------------------------------------------------------ cracks
    def _cracks(self, norm: np.ndarray) -> list[Detection]:
        h, w = norm.shape
        diag = float(np.hypot(h, w))
        k = max(9, int(diag / 90)) | 1
        blackhat = cv2.morphologyEx(
            cv2.GaussianBlur(norm, (3, 3), 0),
            cv2.MORPH_BLACKHAT,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)),
        )
        thr = max(25.0, float(np.percentile(blackhat, 98.5)))
        binary = (blackhat >= thr).astype(np.uint8)
        # Bridge small gaps so one crack is not split into many fragments.
        binary = cv2.morphologyEx(
            binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        )

        n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        # 1) keep thin/elongated fragments
        frags = np.zeros_like(binary)
        frag_info: list[tuple[np.ndarray, float, float, float]] = []
        for i in range(1, n):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < 25:
                continue
            comp = (labels == i).astype(np.uint8)
            (_, _), (rw, rh), _ = cv2.minAreaRect(cv2.findNonZero(comp))
            length, width = max(rw, rh), max(1.0, min(rw, rh))
            fill = area / max(1.0, rw * rh)
            elongation = length / width
            # Cracks are long and thin, or meander (low fill of their box).
            if length < 0.015 * diag or (elongation < 3.0 and fill > 0.35):
                continue
            frags |= comp
            frag_info.append((comp, float(length), float(elongation),
                              float(blackhat[comp > 0].mean()) / 255.0))

        # 2) group fragments that are close to each other into one crack
        gap = max(5, int(0.02 * diag)) | 1
        grouped = cv2.dilate(frags, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (gap, gap)))
        gn, glabels = cv2.connectedComponents(grouped, connectivity=8)
        out: list[Detection] = []
        for g in range(1, gn):
            members = [f for f in frag_info if (glabels[f[0] > 0] == g).any()]
            if not members:
                continue
            total_len = sum(m[1] for m in members)
            if total_len < 0.04 * diag:
                continue
            elongation = max(m[2] for m in members)
            strength = float(np.mean([m[3] for m in members]))
            score = 0.25 + 0.25 * min(1.0, elongation / 15) + 0.2 * min(1.0, strength * 3)
            score += 0.1 * min(1.0, total_len / (0.25 * diag))
            score = round(min(MAX_CONF, score), 2)
            # One editable outline per crack: the grouped band around its fragments.
            mask = (glabels == g).astype(np.uint8)
            for poly in mask_to_polygons(mask, min_area_px=40):
                out.append(
                    Detection(
                        damage_type=DamageType.CRACK,
                        polygon=poly,
                        confidence=score,
                        confidence_source=ConfidenceSource.HEURISTIC,
                        description=(
                            f"خط داكن ممتد طوله التقريبي {total_len / diag:.0%} من قطر الصورة. "
                            "يُرجّح أنه تشقق، ويجب التأكد أنه ليس فاصلًا إنشائيًا أو زخرفة."
                        ),
                        evidence={
                            "length_frac": round(total_len / diag, 3),
                            "elongation": round(elongation, 1),
                            "mean_blackhat": round(strength, 3),
                            "fragments": len(members),
                        },
                    )
                )
                break  # a connected group yields exactly one outline
        return out


    # ---------------------------------------------------------- dark anomalies
    def _dark_anomalies(self, norm: np.ndarray) -> list[Detection]:
        h, w = norm.shape
        bg = cv2.GaussianBlur(norm, (0, 0), sigmaX=max(h, w) / 12)
        diff = bg.astype(np.int16) - cv2.GaussianBlur(norm, (0, 0), 5).astype(np.int16)
        mask = (diff > 28).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
        out: list[Detection] = []
        min_area = 0.004 * h * w
        for poly in mask_to_polygons(mask, min_area_px=int(min_area), epsilon_frac=0.01):
            ys = [p[1] for p in poly]
            xs = [p[0] for p in poly]
            near_base = max(ys) > 0.8
            wide = (max(xs) - min(xs)) > 1.5 * (max(ys) - min(ys))
            hint = (
                " موقعها قرب قاعدة الجدار وامتدادها الأفقي قد يشير إلى رطوبة صاعدة، "
                "لكن ذلك غير مؤكد من الصورة وحدها."
                if near_base and wide
                else ""
            )
            out.append(
                Detection(
                    damage_type=DamageType.UNCERTAIN,
                    polygon=poly,
                    confidence=0.35,
                    confidence_source=ConfidenceSource.HEURISTIC,
                    description=(
                        "منطقة أغمق من محيطها. قد تكون رطوبة أو ظلًا أو فتحة أو ترميمًا سابقًا."
                        + hint
                        + " المعلومات غير كافية لتحديد السبب، ويُنصح بفحص ميداني."
                    ),
                    evidence={"near_base": near_base, "horizontal": wide},
                )
            )
        return out
