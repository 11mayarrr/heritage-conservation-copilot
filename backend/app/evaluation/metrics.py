"""Compare agent proposals with expert-approved regions.

Instance level: a prediction is a true positive when it has the same damage
type as an unmatched expert region and IoU >= iou_threshold (greedy matching).
Pixel level: per-class IoU of the union masks.

These numbers are only meaningful on REAL images with expert-approved
annotations. The system never shows a metric that was not computed this way.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from app.vision.geometry import iou, polygon_mask

RES = 512


def match_instances(preds: list[dict], truth: list[dict], iou_threshold: float = 0.5) -> dict:
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    used: set[int] = set()
    for p in sorted(preds, key=lambda d: -d.get("confidence", 0)):
        best, best_iou = None, 0.0
        for j, t in enumerate(truth):
            if j in used or t["damage_type"] != p["damage_type"]:
                continue
            v = iou(p["polygon"], t["polygon"], RES)
            if v > best_iou:
                best, best_iou = j, v
        if best is not None and best_iou >= iou_threshold:
            used.add(best)
            stats[p["damage_type"]]["tp"] += 1
        else:
            stats[p["damage_type"]]["fp"] += 1
    for j, t in enumerate(truth):
        if j not in used:
            stats[t["damage_type"]]["fn"] += 1
    return dict(stats)


def pixel_iou(preds: list[dict], truth: list[dict]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for cls in {d["damage_type"] for d in preds + truth}:
        pm = np.zeros((RES, RES), np.uint8)
        tm = np.zeros((RES, RES), np.uint8)
        for d in preds:
            if d["damage_type"] == cls:
                pm |= polygon_mask(d["polygon"], RES, RES)
        for d in truth:
            if d["damage_type"] == cls:
                tm |= polygon_mask(d["polygon"], RES, RES)
        out[cls] = {"inter": int((pm & tm).sum()), "union": int((pm | tm).sum())}
    return out


def summarize(counts: dict[str, dict[str, int]], pixels: dict[str, dict[str, int]]) -> dict:
    report = {}
    for cls in sorted(set(counts) | set(pixels)):
        c = counts.get(cls, {"tp": 0, "fp": 0, "fn": 0})
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = (2 * precision * recall / (precision + recall)) if precision and recall else (0.0 if precision is not None and recall is not None else None)
        px = pixels.get(cls, {"inter": 0, "union": 0})
        report[cls] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1,
            "pixel_iou": px["inter"] / px["union"] if px["union"] else None,
        }
    return report
