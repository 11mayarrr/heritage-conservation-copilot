"""Procedural LABELED wall images (synthetic).

Draws a mud-wall-like texture plus five kinds of "damage" with exact pixel
labels. Everything here is invented by code: it contains no real wall and no
real damage. A model trained on it learns THIS generator, so any score measured
on it says nothing about real At-Turaif walls.

Label ids: 0 background, 1 crack, 2 plaster loss, 3 moisture, 4 material loss,
5 edge erosion (see LABEL_TO_DAMAGE).
"""
from __future__ import annotations

import cv2
import numpy as np

from app.models.enums import DamageType

LABEL_TO_DAMAGE: dict[int, DamageType] = {
    1: DamageType.CRACK,
    2: DamageType.PLASTER_LOSS,
    3: DamageType.MOISTURE_EROSION,
    4: DamageType.MATERIAL_LOSS,
    5: DamageType.EDGE_EROSION,
}


def _noise(rng, w, h, scale):
    n = rng.normal(0, 1, (h // scale + 2, w // scale + 2)).astype(np.float32)
    return cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)


def _texture(rng, w, h, base):
    img = np.zeros((h, w, 3), np.float32)
    img[:] = base
    for scale, amp in ((4, 18), (16, 12), (64, 8)):
        img += _noise(rng, w, h, scale)[..., None] * amp
    for _ in range(w * h // 300):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        a, l = rng.uniform(0, np.pi), int(rng.integers(3, 9))
        cv2.line(img, (x, y), (int(x + l * np.cos(a)), int(y + l * np.sin(a))), tuple(float(c) + 25 for c in base), 1)
    return img


def _blob(rng, w, h, cx, cy, rx, ry, rough=0.35, pts=18):
    ang = np.linspace(0, 2 * np.pi, pts, endpoint=False)
    r = 1 + rng.uniform(-rough, rough, pts)
    xs = cx + rx * r * np.cos(ang)
    ys = cy + ry * r * np.sin(ang)
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.stack([xs, ys], 1).astype(np.int32)], 1)
    return m


def make_labeled(seed: int, w: int = 640, h: int = 480) -> tuple[np.ndarray, np.ndarray]:
    """Return (BGR image uint8, label mask uint8)."""
    rng = np.random.default_rng(seed)
    base = np.array([120, 160, 196], np.float32) + rng.uniform(-14, 14, 3).astype(np.float32)
    img = _texture(rng, w, h, base)
    lab = np.zeros((h, w), np.uint8)

    # 3: moisture, a soft dark stain, usually low on the wall.
    if rng.random() < 0.7:
        m = _blob(rng, w, h, rng.uniform(0.2, 0.8) * w, rng.uniform(0.7, 0.95) * h,
                  rng.uniform(0.1, 0.22) * w, rng.uniform(0.05, 0.1) * h, 0.25)
        soft = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 7)
        img *= (1 - 0.38 * soft)[..., None]
        img[..., 0] *= 1 + 0.06 * soft  # slightly bluer / cooler
        lab[m > 0] = 3

    # 2: plaster loss, exposed rougher, redder substrate with a dark rim.
    for _ in range(int(rng.integers(0, 3))):
        m = _blob(rng, w, h, rng.uniform(0.15, 0.85) * w, rng.uniform(0.15, 0.7) * h,
                  rng.uniform(0.05, 0.11) * w, rng.uniform(0.05, 0.11) * h, 0.4)
        under = _texture(rng, w, h, base * np.array([0.82, 0.9, 1.08], np.float32))
        under += _noise(rng, w, h, 3)[..., None] * 16
        img[m > 0] = under[m > 0]
        rim = cv2.dilate(m, np.ones((5, 5), np.uint8)) - m
        img[rim > 0] *= 0.72
        lab[m > 0] = 2

    # 4: material loss, deep dark hole with a shadowed interior.
    for _ in range(int(rng.integers(0, 2))):
        m = _blob(rng, w, h, rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.7) * h,
                  rng.uniform(0.03, 0.07) * w, rng.uniform(0.03, 0.07) * h, 0.45, 12)
        depth = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 4)
        img *= (1 - 0.7 * depth)[..., None]
        lab[m > 0] = 4

    # 5: edge erosion, a bite out of the top or a side showing the bright sky.
    if rng.random() < 0.55:
        m = np.zeros((h, w), np.uint8)
        for _ in range(int(rng.integers(2, 5))):
            cx = rng.uniform(0.05, 0.95) * w
            m |= _blob(rng, w, h, cx, 0, rng.uniform(0.04, 0.09) * w, rng.uniform(0.04, 0.09) * h, 0.4, 12)
        img[m > 0] = np.array([235, 215, 190], np.float32) + _noise(rng, w, h, 8)[m > 0][:, None] * 4
        lab[m > 0] = 5

    # 1: cracks last so they stay visible on top of everything but holes/sky.
    for _ in range(int(rng.integers(1, 4))):
        x, y = rng.uniform(0.1, 0.9) * w, rng.uniform(0.05, 0.4) * h
        angle, pts = rng.uniform(1.0, 2.1), [(x, y)]
        for _ in range(int(rng.integers(18, 40))):
            angle = float(np.clip(angle + rng.normal(0, 0.3), 0.6, 2.5))
            x, y = x + 11 * np.cos(angle), y + 11 * np.sin(angle)
            pts.append((x, y))
        line = np.zeros((h, w), np.uint8)
        width = int(rng.integers(2, 4))
        cv2.polylines(line, [np.array(pts, np.int32)], False, 1, width, cv2.LINE_AA)
        keep = (line > 0) & (lab != 4) & (lab != 5)
        img[keep] = np.array([40, 52, 66], np.float32)
        lab[keep] = 1

    img = cv2.GaussianBlur(img, (0, 0), 0.6)
    img = img * rng.uniform(0.9, 1.1) + rng.uniform(-8, 8)
    return np.clip(img, 0, 255).astype(np.uint8), lab
