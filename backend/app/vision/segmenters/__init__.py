from __future__ import annotations

import logging

from app.config import get_settings
from app.vision.segmenters.base import (
    PromptSegmenter,
    SegmenterInfo,
    SegmenterUnavailable,
    SegmentResult,
    validate_prompts,
)
from app.vision.segmenters.grabcut import GrabCutSegmenter

__all__ = ["PromptSegmenter", "SegmentResult", "SegmenterInfo", "SegmenterUnavailable",
           "get_segmenter", "validate_prompts", "reset_segmenter"]

log = logging.getLogger(__name__)
_segmenter: PromptSegmenter | None = None
_fallback_reason: str | None = None


def get_segmenter() -> PromptSegmenter:
    """HCC_SEGMENTER: "auto" (SAM 2 if configured, else GrabCut), "sam2", or "grabcut"."""
    global _segmenter, _fallback_reason
    if _segmenter is not None:
        return _segmenter
    choice = get_settings().segmenter
    if choice in ("auto", "sam2"):
        try:
            from app.vision.segmenters.sam2_adapter import Sam2Segmenter

            _segmenter = Sam2Segmenter()
            return _segmenter
        except SegmenterUnavailable as e:
            if choice == "sam2":
                raise
            _fallback_reason = str(e)
            log.info("SAM 2 unavailable, using GrabCut: %s", e)
    _segmenter = GrabCutSegmenter()
    return _segmenter


def fallback_reason() -> str | None:
    return _fallback_reason


def reset_segmenter(seg: PromptSegmenter | None = None) -> None:
    global _segmenter, _fallback_reason
    _segmenter, _fallback_reason = seg, None
