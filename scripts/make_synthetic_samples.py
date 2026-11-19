"""Generate SYNTHETIC wall images for tests and demos.

These are procedurally drawn textures (no real wall, no real damage). They exist
only to exercise the pipeline end-to-end. Never present results on them as
findings. Real At-Turaif photos go in sample_data/real/ (see sample_data/README.md).

Usage: python scripts/make_synthetic_samples.py [out_dir]
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np


def mud_texture(w: int, h: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.zeros((h, w, 3), np.float32)
    base[:] = (120, 160, 196)  # BGR sandy clay
    for scale, amp in ((4, 22), (16, 14), (64, 8)):
        n = rng.normal(0, 1, (h // scale + 2, w // scale + 2)).astype(np.float32)
        n = cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
        base += n[..., None] * amp
    # Straw flecks
    for _ in range(1500):
        x, y = rng.integers(0, w), rng.integers(0, h)
        ang = rng.uniform(0, np.pi)
        l = rng.integers(4, 12)
        cv2.line(base, (x, y), (int(x + l * np.cos(ang)), int(y + l * np.sin(ang))), (150, 190, 215), 1)
    return np.clip(base, 0, 255).astype(np.uint8)


def draw_crack(img, start, steps, rng, width=3, step_len=14, drift=0.35, angle=1.35):
    x, y = start
    pts = [(x, y)]
    for _ in range(steps):
        angle += rng.normal(0, drift)
        angle = float(np.clip(angle, 0.7, 2.4))
        x += int(step_len * np.cos(angle))
        y += int(step_len * np.sin(angle))
        pts.append((x, y))
    cv2.polylines(img, [np.array(pts, np.int32)], False, (40, 52, 66), width, cv2.LINE_AA)
    return pts


def make_pair(out: Path, w=1600, h=1200, seed=7):
    rng = np.random.default_rng(seed)
    before = mud_texture(w, h, seed)
    # Darker basal band (moisture-like staining) with soft edge.
    band = np.zeros((h, w), np.float32)
    band[int(h * 0.82):, int(w * 0.1):int(w * 0.75)] = 1
    band = cv2.GaussianBlur(band, (0, 0), 25)
    before = (before * (1 - 0.45 * band[..., None])).astype(np.uint8)
    crack_rng = np.random.default_rng(seed + 1)
    draw_crack(before, (int(w * 0.35), int(h * 0.12)), 30, crack_rng)

    after = before.copy()
    # Crack grows and a new one appears.
    draw_crack(after, (int(w * 0.35), int(h * 0.12)), 48, np.random.default_rng(seed + 1))
    draw_crack(after, (int(w * 0.70), int(h * 0.20)), 25, np.random.default_rng(seed + 5), angle=1.8)
    # Different lighting + small viewpoint change on the second visit.
    after = cv2.convertScaleAbs(after, alpha=1.12, beta=-8)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), 2.0, 1.02)
    M[:, 2] += (18, -12)
    after = cv2.warpAffine(after, M, (w, h), borderMode=cv2.BORDER_REFLECT)

    out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out / "synthetic_wall_T1.jpg"), before, [cv2.IMWRITE_JPEG_QUALITY, 92])
    cv2.imwrite(str(out / "synthetic_wall_T2.jpg"), after, [cv2.IMWRITE_JPEG_QUALITY, 92])
    blurry = cv2.GaussianBlur(before, (0, 0), 9)
    cv2.imwrite(str(out / "synthetic_blurry.jpg"), blurry)
    dark = (before * 0.12).astype(np.uint8)
    cv2.imwrite(str(out / "synthetic_dark.jpg"), dark)
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "sample_data" / "synthetic"
    print("wrote", make_pair(target))
