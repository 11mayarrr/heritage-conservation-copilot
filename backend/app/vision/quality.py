"""Image Quality Assessment: sharpness, exposure, resolution and a rough camera tilt.

Thresholds are starting values chosen for a demo; they must be tuned on real
At-Turaif photos before field use (see README, "Limitations")."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import cv2
import numpy as np

from app.config import get_settings
from app.vision.imageio import resize_max
from app.vision.tilt import PARTIAL, STRONG, UNMEASURABLE, estimate_tilt


@dataclass
class QualityReport:
    acceptable: bool
    width: int
    height: int
    sharpness: float
    brightness: float
    clipped_dark: float
    clipped_bright: float
    contrast: float
    issues: list[str] = field(default_factory=list)  # blocking, Arabic
    warnings: list[str] = field(default_factory=list)  # non-blocking, Arabic
    tilt: dict | None = None  # rough camera-tilt estimate; None when the image was rejected

    def to_dict(self) -> dict:
        return asdict(self)


def assess_quality(img: np.ndarray) -> QualityReport:
    s = get_settings()
    h, w = img.shape[:2]
    small, _ = resize_max(img, 1024)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    contrast = float(gray.std())
    clipped_dark = float((gray <= 8).mean())
    clipped_bright = float((gray >= 247).mean())

    issues: list[str] = []
    warnings: list[str] = []

    if w < s.min_width or h < s.min_height:
        issues.append(
            f"دقة الصورة منخفضة ({w}×{h}). الحد الأدنى {s.min_width}×{s.min_height}."
        )
    if sharpness < s.blur_threshold:
        issues.append("الصورة غير واضحة (ضبابية أو اهتزاز). أعد التصوير مع تثبيت الكاميرا.")
    elif sharpness < s.blur_threshold * 2:
        warnings.append("وضوح الصورة متوسط، قد تفوت التشققات الدقيقة.")
    if brightness < s.dark_threshold:
        issues.append("الصورة مظلمة جدًا. صوّر في إضاءة أفضل أو بدون ظل مباشر.")
    elif brightness > s.bright_threshold:
        issues.append("الصورة شديدة السطوع. تجنب أشعة الشمس المباشرة على العدسة.")
    if clipped_bright > s.clipped_fraction_max:
        issues.append("جزء كبير من الصورة محترق ضوئيًا (أبيض بالكامل).")
    if clipped_dark > s.clipped_fraction_max:
        issues.append("جزء كبير من الصورة معتم بالكامل (ظل قوي).")
    if contrast < 18:
        warnings.append("تباين الصورة منخفض، قد يصعب تمييز حدود التلف.")
    tilt = None
    if not issues:  # a rejected image is retaken anyway
        est = estimate_tilt(
            img, focal_factor=s.tilt_focal_factor, frontal_deg=s.tilt_frontal_deg, warn_deg=s.tilt_warn_deg
        )
        tilt = est.to_dict()
        if est.status in (STRONG, PARTIAL, UNMEASURABLE):
            warnings.append(est.note_ar)  # warning only: the tilt never blocks an image

    return QualityReport(
        acceptable=not issues,
        width=w,
        height=h,
        sharpness=round(sharpness, 1),
        brightness=round(brightness, 1),
        clipped_dark=round(clipped_dark, 4),
        clipped_bright=round(clipped_bright, 4),
        contrast=round(contrast, 1),
        issues=issues,
        warnings=warnings,
        tilt=tilt,
    )
