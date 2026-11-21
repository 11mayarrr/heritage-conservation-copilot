from __future__ import annotations

from app.config import get_settings
from app.vision.detectors.base import DamageDetector, Detection, DetectorInfo
from app.vision.detectors.heuristic import HeuristicDetector
from app.vision.detectors.mock import MockDetector

__all__ = ["DamageDetector", "Detection", "DetectorInfo", "get_detector"]


def get_detector(name: str | None = None) -> DamageDetector:
    name = name or get_settings().detector
    if name == "mock":
        return MockDetector()
    if name == "heuristic":
        return HeuristicDetector()
    if name == "model":
        from app.vision.detectors.segmentation_model import YoloSegDetector

        return YoloSegDetector()
    if name == "synthetic_model":
        from app.vision.detectors.pixel_model import SyntheticPixelDetector

        return SyntheticPixelDetector()
    raise ValueError(f"unknown detector: {name}")
