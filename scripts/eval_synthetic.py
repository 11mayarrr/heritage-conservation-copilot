"""Evaluate the synthetic-trained model on HELD-OUT synthetic images.

Usage: python scripts/eval_synthetic.py [--n 40] [--out docs/synthetic_eval.json]

Crack instances use a 5 px tolerance (see truth_regions).
These numbers measure how well the model reproduces the synthetic generator.
They are NOT accuracy on real At-Turaif walls and must never be shown as such.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.evaluation.metrics import match_instances, pixel_iou, summarize  # noqa: E402
from app.vision.detectors.pixel_model import SyntheticPixelDetector  # noqa: E402
from app.vision.geometry import mask_to_polygons  # noqa: E402
from app.vision.synthetic import LABEL_TO_DAMAGE, make_labeled  # noqa: E402

HELD_OUT_START = 100_000


def truth_regions(lab: np.ndarray) -> list[dict]:
    out = []
    for cid, dtype in LABEL_TO_DAMAGE.items():
        m = (lab == cid).astype(np.uint8)
        if cid == 1:
            # Tolerance for thin structures: a 3 px line cannot be matched at IoU 0.5
            # by a mask that is off by a pixel, so cracks are compared after a small
            # dilation (applied to the truth; the detector merges fragments itself).
            m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        n, comp = cv2.connectedComponents(m)
        for k in range(1, n):
            cm = (comp == k).astype(np.uint8)
            if cm.sum() < 20:
                continue
            for poly in mask_to_polygons(cm, min_area_px=20):
                out.append({"damage_type": dtype.value, "polygon": poly, "confidence": 1.0})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    det = SyntheticPixelDetector()
    counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    pixels = defaultdict(lambda: {"inter": 0, "union": 0})
    for seed in range(HELD_OUT_START, HELD_OUT_START + args.n):
        img, lab = make_labeled(seed)
        preds = [{"damage_type": d.damage_type.value, "polygon": d.polygon, "confidence": d.confidence}
                 for d in det.detect(img)]
        truth = truth_regions(lab)
        for cls, s in match_instances(preds, truth, args.iou).items():
            for k in s:
                counts[cls][k] += s[k]
        for cls, s in pixel_iou(preds, truth).items():
            for k in s:
                pixels[cls][k] += s[k]
    report = {
        "note": "SYNTHETIC held-out images only; not accuracy on real walls.",
        "held_out_images": args.n,
        "iou_threshold": args.iou,
        "per_type": summarize(counts, pixels),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
