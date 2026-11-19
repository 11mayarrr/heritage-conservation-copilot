"""Evaluate the agent against expert-approved inspections.

Usage (from repo root):  python scripts/evaluate.py [--iou 0.5] [--include-synthetic]

Uses only inspections with status "approved". Prints Precision, Recall, F1 and
pixel IoU per damage type. Results on synthetic images are excluded by default
because they say nothing about performance on real At-Turaif walls.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.database import session as dbs  # noqa: E402
from app.database.models import Inspection, Wall  # noqa: E402
from app.evaluation.metrics import match_instances, pixel_iou, summarize  # noqa: E402
from app.models.enums import RegionStatus  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--include-synthetic", action="store_true")
    args = ap.parse_args()

    dbs.init_engine()
    db = next(dbs.get_db())
    counts: dict = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    pixels: dict = defaultdict(lambda: {"inter": 0, "union": 0})
    n = 0
    for insp in db.scalars(select(Inspection).where(Inspection.status == "approved")):
        wall: Wall = insp.wall
        if not args.include_synthetic and wall.code.upper().startswith("SYN"):
            continue
        preds = (insp.analysis or {}).get("agent_detections", [])
        truth = [{"damage_type": r.damage_type, "polygon": r.polygon}
                 for r in insp.regions if r.status == RegionStatus.APPROVED.value]
        for cls, c in match_instances(preds, truth, args.iou).items():
            for k in c:
                counts[cls][k] += c[k]
        for cls, p in pixel_iou(preds, truth).items():
            pixels[cls]["inter"] += p["inter"]
            pixels[cls]["union"] += p["union"]
        n += 1
    if n == 0:
        print("No approved inspections to evaluate. No metrics are reported.")
        return
    print(json.dumps({"approved_inspections": n, "iou_threshold": args.iou,
                      "per_class": summarize(dict(counts), dict(pixels))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
