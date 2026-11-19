"""Face anonymization, applied before any analysis or storage.

Detection uses OpenCV Haar cascades (frontal + profile, mirrored) because they
ship with no extra download. They miss small, turned or occluded faces, so the
UI always shows a privacy notice and the expert can add manual blur boxes.
If `backend/app/privacy/models/face_detection_yunet_2023mar.onnx` exists, the
more accurate YuNet detector is used instead (see scripts/download_models.py).

Faces are only located and hidden: no identity, tracking, or behavior analysis.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

MODELS_DIR = Path(__file__).parent / "models"


@dataclass
class Box:
    x: int
    y: int
    w: int
    h: int


def _merge(boxes: list[Box]) -> list[Box]:
    out: list[Box] = []
    for b in sorted(boxes, key=lambda b: -b.w * b.h):
        cx, cy = b.x + b.w / 2, b.y + b.h / 2
        if any(o.x <= cx <= o.x + o.w and o.y <= cy <= o.y + o.h for o in out):
            continue
        out.append(b)
    return out


class FaceDetector:
    def __init__(self) -> None:
        self._yunet = None
        yunet_path = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
        if yunet_path.exists():
            try:
                self._yunet = cv2.FaceDetectorYN.create(str(yunet_path), "", (320, 320), 0.6)
            except cv2.error:
                self._yunet = None
        self._frontal = cv2.CascadeClassifier(
            str(MODELS_DIR / "haarcascade_frontalface_default.xml")
        )
        self._profile = cv2.CascadeClassifier(str(MODELS_DIR / "haarcascade_profileface.xml"))
        if self._frontal.empty() or self._profile.empty():
            raise RuntimeError("face cascade files missing from privacy/models")

    @property
    def method(self) -> str:
        return "yunet" if self._yunet is not None else "haar_cascade"

    def detect(self, img: np.ndarray) -> list[Box]:
        h, w = img.shape[:2]
        scale = min(1.0, 1600 / max(h, w))
        small = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1 else img
        boxes: list[Box] = []
        if self._yunet is not None:
            sh, sw = small.shape[:2]
            self._yunet.setInputSize((sw, sh))
            _, faces = self._yunet.detect(small)
            for f in faces if faces is not None else []:
                x, y, bw, bh = (int(v / scale) for v in f[:4])
                boxes.append(Box(x, y, bw, bh))
        else:
            gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
            min_size = (max(20, small.shape[1] // 60),) * 2
            found = list(self._frontal.detectMultiScale(gray, 1.1, 6, minSize=min_size))
            found += list(self._profile.detectMultiScale(gray, 1.1, 6, minSize=min_size))
            flipped = cv2.flip(gray, 1)
            for x, y, bw, bh in self._profile.detectMultiScale(flipped, 1.1, 6, minSize=min_size):
                found.append((gray.shape[1] - x - bw, y, bw, bh))
            for x, y, bw, bh in found:
                boxes.append(
                    Box(int(x / scale), int(y / scale), int(bw / scale), int(bh / scale))
                )
        return _merge(boxes)


def _pad(b: Box, img_w: int, img_h: int, pad: float = 0.25) -> tuple[int, int, int, int]:
    px, py = int(b.w * pad), int(b.h * pad)
    x0, y0 = max(0, b.x - px), max(0, b.y - py)
    x1, y1 = min(img_w, b.x + b.w + px), min(img_h, b.y + b.h + py)
    return x0, y0, x1, y1


def hide_region(img: np.ndarray, x0: int, y0: int, x1: int, y1: int, method: str) -> None:
    roi = img[y0:y1, x0:x1]
    if roi.size == 0:
        return
    if method == "pixelate":
        rh, rw = roi.shape[:2]
        tiny = cv2.resize(roi, (max(1, rw // 12), max(1, rh // 12)), interpolation=cv2.INTER_LINEAR)
        img[y0:y1, x0:x1] = cv2.resize(tiny, (rw, rh), interpolation=cv2.INTER_NEAREST)
    else:
        k = max(31, (max(roi.shape[:2]) // 2) | 1)
        img[y0:y1, x0:x1] = cv2.GaussianBlur(roi, (k, k), 0)


_detector: FaceDetector | None = None


def get_face_detector() -> FaceDetector:
    global _detector
    if _detector is None:
        _detector = FaceDetector()
    return _detector


def anonymize(img: np.ndarray, method: str = "blur") -> tuple[np.ndarray, dict]:
    """Return a copy with faces hidden plus a privacy summary (box count only,
    no face crops are kept)."""
    det = get_face_detector()
    out = img.copy()
    h, w = img.shape[:2]
    boxes = det.detect(img)
    for b in boxes:
        hide_region(out, *_pad(b, w, h), method=method)
    return out, {
        "faces_hidden": len(boxes),
        "method": method,
        "detector": det.method,
        "boxes": [[b.x / w, b.y / h, b.w / w, b.h / h] for b in boxes],
        "original_stored": False,
        "notice": "تم إخفاء الوجوه آليًا. قد يفوت الكاشف وجوهًا صغيرة أو جانبية؛ "
        "راجع الصورة وأضف إخفاءً يدويًا عند الحاجة.",
    }


def apply_manual_boxes(img: np.ndarray, boxes: list[list[float]], method: str = "blur") -> np.ndarray:
    """Hide extra areas the expert marked (normalized x, y, w, h)."""
    out = img.copy()
    h, w = img.shape[:2]
    for bx, by, bw, bh in boxes:
        x0, y0 = int(bx * w), int(by * h)
        hide_region(out, x0, y0, int((bx + bw) * w), int((by + bh) * h), method)
    return out
