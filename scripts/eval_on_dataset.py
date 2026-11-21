"""Evaluate pixel models on the HELD-OUT part of a stored dataset (task C6).

Scores only rows whose split is "test" (never used by scripts/train_on_dataset.py).
Reports each model separately. These numbers measure how well a model reproduces the
code-drawn generator. They are NOT accuracy on real At-Turaif walls. Results on real
photos are a separate section and stay empty until expert-approved real images exist (D3).

Usage: python scripts/eval_on_dataset.py [--data sample_data/generated_procedural]
       [--weights NAME=PATH ...] [--out-json docs/EVALUATION_GENERATED.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.evaluation.metrics import match_instances, pixel_iou, summarize  # noqa: E402
from app.vision.detectors.pixel_model import DEFAULT_WEIGHTS, SyntheticPixelDetector  # noqa: E402
from eval_synthetic import truth_regions  # noqa: E402
from train_on_dataset import DEFAULT_DATA, DEFAULT_OUT, read_manifest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def evaluate(det, data: Path, rows: list[dict], iou: float = 0.5) -> dict:
    counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    pixels = defaultdict(lambda: {"inter": 0, "union": 0})
    for r in rows:
        img = cv2.imread(str(data / "images" / f"{r['name']}.jpg"))
        lab = cv2.imread(str(data / "labels" / f"{r['name']}.png"), cv2.IMREAD_GRAYSCALE)
        preds = [{"damage_type": d.damage_type.value, "polygon": d.polygon, "confidence": d.confidence} for d in det.detect(img)]
        truth = truth_regions(lab)
        for cls, s in match_instances(preds, truth, iou).items():
            for k in s:
                counts[cls][k] += s[k]
        for cls, s in pixel_iou(preds, truth).items():
            for k in s:
                pixels[cls][k] += s[k]
    return summarize(counts, pixels)


def macro(per_type: dict, key: str) -> float:
    vals = [v[key] for v in per_type.values() if v.get(key) is not None]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--weights", nargs="*", default=[f"trained_on_this_dataset={DEFAULT_OUT}", f"older_model_narrow_generator={DEFAULT_WEIGHTS}"])
    ap.add_argument("--out-json", type=Path, default=ROOT / "docs" / "EVALUATION_GENERATED.json")
    args = ap.parse_args()

    rows = [r for r in read_manifest(args.data) if r["split"] == "test"]
    report = {
        "note": "Held-out CODE-DRAWN images only. Not accuracy on real At-Turaif walls.",
        "dataset": args.data.name,
        "test_images": len(rows),
        "iou_threshold": 0.5,
        "models": {},
        "real_images": {"images": 0, "result": None, "why": "no expert-approved real images exist yet (plan D3)"},
    }
    for item in args.weights:
        name, path = item.split("=", 1)
        per_type = evaluate(SyntheticPixelDetector(path), args.data, rows)
        report["models"][name] = {"weights": Path(path).name, "macro_f1": macro(per_type, "f1"),
                                  "macro_pixel_iou": macro(per_type, "pixel_iou"), "per_type": per_type}
    print(json.dumps({k: (v if k != "models" else {m: {x: y for x, y in d.items() if x != "per_type"} for m, d in v.items()}) for k, v in report.items()}, ensure_ascii=False, indent=2))
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
