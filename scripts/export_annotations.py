"""Export expert-approved regions as COCO-style polygons for training a
custom segmentation model (YOLO-seg / SegFormer).

Usage: python scripts/export_annotations.py out_dir
Writes out_dir/annotations.json and copies the anonymized images.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.database import session as dbs  # noqa: E402
from app.database.models import Inspection  # noqa: E402
from app.models.enums import DamageType, RegionStatus  # noqa: E402
from app.services.storage import get_storage  # noqa: E402
from app.vision.geometry import polygon_area  # noqa: E402

CATEGORIES = [t for t in DamageType if t is not DamageType.UNCERTAIN]


def main(out: Path) -> None:
    dbs.init_engine()
    db = next(dbs.get_db())
    (out / "images").mkdir(parents=True, exist_ok=True)
    coco = {"images": [], "annotations": [],
            "categories": [{"id": i, "name": t.value} for i, t in enumerate(CATEGORIES)]}
    cat_id = {t.value: i for i, t in enumerate(CATEGORIES)}
    ann_id = 0
    for img_id, insp in enumerate(db.scalars(select(Inspection).where(Inspection.status == "approved"))):
        if not insp.image_key:
            continue
        name = f"{insp.case_number}.jpg"
        shutil.copy(get_storage().path(insp.image_key), out / "images" / name)
        coco["images"].append({"id": img_id, "file_name": name, "width": insp.width, "height": insp.height,
                               "wall": insp.wall.code, "captured_at": insp.captured_at.isoformat()})
        for r in insp.regions:
            if r.status != RegionStatus.APPROVED.value or r.damage_type not in cat_id:
                continue  # uncertain regions are not training labels
            seg = [c for x, y in r.polygon for c in (x * insp.width, y * insp.height)]
            xs, ys = seg[0::2], seg[1::2]
            coco["annotations"].append({
                "id": ann_id, "image_id": img_id, "category_id": cat_id[r.damage_type],
                "segmentation": [seg], "area": polygon_area(r.polygon) * insp.width * insp.height,
                "bbox": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)], "iscrowd": 0})
            ann_id += 1
    (out / "annotations.json").write_text(json.dumps(coco, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"exported {len(coco['images'])} images, {ann_id} annotations to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "export"))
