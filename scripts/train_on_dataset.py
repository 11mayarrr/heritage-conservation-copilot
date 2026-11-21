"""Train the pixel classifier on a STORED labeled dataset (task C5).

Reads <data>/images + <data>/labels + <data>/manifest.jsonl, trains ONLY on rows whose split is "train",
and writes the weights plus a training log (data counts, seeds, time, library versions).

Works with the output of scripts/generate_procedural_dataset.py or scripts/generate_ai_dataset.py.
The result learns that dataset's generator, not real walls (see docs/PROCEDURAL_DATASET.md).

Usage: python scripts/train_on_dataset.py [--data sample_data/generated_procedural] [--out PATH]
Use it afterwards with: HCC_DETECTOR=synthetic_model HCC_PIXEL_WEIGHTS=<out> (output stays tagged unvalidated).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import joblib
import numpy as np
import sklearn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402

from app.vision.detectors.pixel_model import FEAT_SCALE, extract_features  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "sample_data" / "generated_procedural"
DEFAULT_OUT = ROOT / "backend" / "app" / "vision" / "detectors" / "weights" / "generated_pixel_hgb.joblib"
PER_CLASS_PER_IMAGE = 2500


def read_manifest(data: Path) -> list[dict]:
    path = data / "manifest.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Generate the dataset first (scripts/generate_procedural_dataset.py).")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def train(data: Path, out: Path, seed: int = 0) -> dict:
    rows = [r for r in read_manifest(data) if r["split"] == "train"]
    if not rows:
        raise ValueError("no training rows in the manifest")
    rng = np.random.default_rng(seed)
    X, y = [], []
    t0 = time.time()
    for r in rows:
        img = cv2.imread(str(data / "images" / f"{r['name']}.jpg"))
        lab = cv2.imread(str(data / "labels" / f"{r['name']}.png"), cv2.IMREAD_GRAYSCALE)
        f = extract_features(img)
        small = cv2.resize(lab, None, fx=FEAT_SCALE, fy=FEAT_SCALE, interpolation=cv2.INTER_NEAREST).reshape(-1)
        for c in np.unique(small):
            idx = np.flatnonzero(small == c)
            take = rng.choice(idx, min(len(idx), PER_CLASS_PER_IMAGE), replace=False)
            X.append(f[take])
            y.append(np.full(len(take), c, np.uint8))
    X, y = np.concatenate(X), np.concatenate(y)
    clf = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.12, max_leaf_nodes=24,
                                         class_weight="balanced", random_state=seed)
    clf.fit(X, y)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, out, compress=3)
    classes, counts = np.unique(y, return_counts=True)
    log = {
        "note": "Trained on a stored dataset drawn by code. Not real walls; no accuracy claim on At-Turaif.",
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": str(data.name),
        "train_images": len(rows),
        "test_images_not_used": sum(1 for r in read_manifest(data) if r["split"] == "test"),
        "sampled_pixels_by_class": {int(c): int(n) for c, n in zip(classes, counts)},
        "model": "HistGradientBoostingClassifier(max_iter=120, learning_rate=0.12, max_leaf_nodes=24, class_weight=balanced)",
        "sklearn": sklearn.__version__,
        "seed": seed,
        "seconds": round(time.time() - t0, 1),
        "weights": out.name,
        "weights_mb": round(out.stat().st_size / 1e6, 2),
    }
    out.with_suffix(".train_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    return log


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    print(json.dumps(train(args.data, args.out, args.seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
