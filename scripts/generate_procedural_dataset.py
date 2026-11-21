"""Write a LABELED dataset of CODE-DRAWN wall images to disk (task C4, code-only path).

Nothing here comes from a photo or from an AI image model. Every image is drawn by
backend/app/vision/synthetic.py and every label is exact by construction. A model
trained and scored on it says nothing about real At-Turaif walls (docs/PROCEDURAL_DATASET.md).

Layout (same as scripts/generate_ai_dataset.py, so the training script reads either):
  <out>/images/gen_proc_<type>_<NNNN>.jpg   <out>/labels/<same name>.png (0 = background, 1-5 = damage)
  <out>/meta/<same name>.json   <out>/manifest.jsonl   <out>/summary.json

Usage: python scripts/generate_procedural_dataset.py [--per-type 200] [--out sample_data/generated_procedural]
Deterministic: the same arguments always produce the same files.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.vision.synthetic import LABEL_TO_DAMAGE, make_labeled_varied  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "sample_data" / "generated_procedural"
GENERATOR = "procedural-code: backend/app/vision/synthetic.py make_labeled_varied"
TEST_EVERY = 5  # every 5th image of each type is a test image (20%)
NOTE = "Drawn by code. Not a real wall. Do not report scores on it as accuracy on At-Turaif."


def split_of(index: int) -> str:
    return "test" if index % TEST_EVERY == TEST_EVERY - 1 else "train"


def build(out: Path, per_type: int) -> dict:
    for sub in ("images", "labels", "meta"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for label_id, damage in sorted(LABEL_TO_DAMAGE.items()):
        for i in range(per_type):
            seed = label_id * 100_000 + i  # fixed seed per (type, index): reruns give identical files
            img, lab, used = make_labeled_varied(seed, focus=label_id)
            name = f"gen_proc_{damage.value}_{i + 1:04d}"
            cv2.imwrite(str(out / "images" / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            cv2.imwrite(str(out / "labels" / f"{name}.png"), lab)
            present = sorted(int(v) for v in set(lab.ravel().tolist()) if v)
            meta = {
                "source": "generated",
                "name": name,
                "generated_by": GENERATOR,
                "date": date,
                "seed": seed,
                "seed_used": used,
                "prompt": None,
                "focus_damage_type": damage.value,
                "label_ids_present": present,
                "split": split_of(i),
                "expert_review": "none: drawn by code, nothing to review for realism",
                "note": NOTE,
            }
            (out / "meta" / f"{name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            rows.append(meta)
    (out / "manifest.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    summary = {
        "source": "generated",
        "generated_by": GENERATOR,
        "date": date,
        "images": len(rows),
        "per_focus_type": {d.value: per_type for _, d in sorted(LABEL_TO_DAMAGE.items())},
        "by_split": {s: sum(r["split"] == s for r in rows) for s in ("train", "test")},
        "note": NOTE,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-type", type=int, default=200, help="images per damage type (5 types)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    summary = build(args.out, args.per_type)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("صور مرسومة بالكود وليست جدرانًا حقيقية.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
