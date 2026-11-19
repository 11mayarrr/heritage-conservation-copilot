"""Detector interface. Every damage detector (mock, OpenCV heuristic, or a
trained segmentation model added later) returns the same structure, so the
rest of the system does not change when the model is replaced."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from app.models.enums import ConfidenceSource, DamageType


@dataclass
class Detection:
    damage_type: DamageType
    polygon: list[list[float]]  # normalized 0..1
    confidence: float
    confidence_source: ConfidenceSource
    description: str
    evidence: dict = field(default_factory=dict)


@dataclass
class DetectorInfo:
    name: str
    kind: str  # "mock" | "heuristic" | "model"
    version: str
    validated: bool  # True only after evaluation against expert annotations
    disclaimer: str  # Arabic, shown in UI and report


class DamageDetector(Protocol):
    info: DetectorInfo

    def detect(self, img: np.ndarray) -> list[Detection]: ...
