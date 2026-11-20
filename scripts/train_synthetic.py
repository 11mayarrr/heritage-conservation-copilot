"""Train the pixel classifier on SYNTHETIC labeled images.

Usage: python scripts/train_synthetic.py [--n-train 150] [--out PATH]

Train seeds 0..n-1; evaluation uses disjoint seeds (see eval_synthetic.py).
The result learns the generator in backend/app/vision/synthetic.py, not real walls.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402

from app.vision.detectors.pixel_model import DEFAULT_WEIGHTS, FEAT_SCALE, extract_features  # noqa: E402
from app.vision.synthetic import make_labeled  # noqa: E402

PER_CLASS_PER_IMAGE = 2500


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-train", type=int, default=150)
    ap.add_argument("--out", type=Path, default=DEFAULT_WEIGHTS)
    args = ap.parse_args()

    rng = np.random.default_rng(0)
    X, y = [], []
    t0 = time.time()
    for seed in range(args.n_train):
        img, lab = make_labeled(seed)
        f = extract_features(img)
        small = cv2.resize(lab, None, fx=FEAT_SCALE, fy=FEAT_SCALE, interpolation=cv2.INTER_NEAREST).reshape(-1)
        for c in np.unique(small):
            idx = np.flatnonzero(small == c)
            take = rng.choice(idx, min(len(idx), PER_CLASS_PER_IMAGE), replace=False)
            X.append(f[take])
            y.append(np.full(len(take), c, np.uint8))
    X, y = np.concatenate(X), np.concatenate(y)
    print(f"{len(y)} pixels from {args.n_train} images, classes:", dict(zip(*np.unique(y, return_counts=True))))
    clf = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.12, max_leaf_nodes=24,
                                         class_weight="balanced", random_state=0)
    clf.fit(X, y)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, args.out, compress=3)
    print(f"saved {args.out} ({args.out.stat().st_size / 1e6:.2f} MB) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
