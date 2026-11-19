"""Self-contained HTML report (images embedded) that can be printed to PDF
from any browser."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.rules import PRIORITY_RULES_AR
from app.database.models import AuditEntry, Inspection
from app.models.enums import (
    DAMAGE_COLORS,
    DAMAGE_LABELS_AR,
    INSUFFICIENT_INFO_AR,
    PRELIMINARY_WARNING_AR,
    DamageType,
    RegionStatus,
)
from app.rag.knowledge_base import get_kb
from app.services.audit import serialize
from app.services.inspections import inspection_out
from app.services.storage import get_storage
from app.vision.imageio import decode_image, encode_jpeg, resize_max
from app.vision.render import render_atlas

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)

STATUS_AR = {
    "in_review": "قيد المراجعة",
    "approved": "معتمدة",
    "returned": "أعيدت للمراجعة",
    "rejected_quality": "مرفوضة لجودة الصورة",
}
PRIORITY_AR = {"high": "عالية", "medium": "متوسطة", "low": "منخفضة"}
CONF_SOURCE_AR = {
    "mock": "وهمية (عرض)",
    "heuristic_uncalibrated": "تقديرية غير معايرة",
    "model_unvalidated": "نموذج غير مُقيّم",
    "expert": "حددها المختص",
}


def _b64(img) -> str:
    small, _ = resize_max(img, 1600)
    return "data:image/jpeg;base64," + base64.b64encode(encode_jpeg(small, 85)).decode()


def atlas_image(insp: Inspection, legend: bool = True):
    img = decode_image(get_storage().get(insp.image_key))
    data = inspection_out(insp)
    grid = (insp.grid.get("cols", 6), insp.grid.get("rows", 4)) if insp.grid else None
    return img, render_atlas(img, data["regions"], grid=grid, legend=legend)


def build_report(db: Session, insp: Inspection) -> str:
    data = inspection_out(insp)
    kb = get_kb()
    image_b64 = atlas_b64 = None
    if insp.image_key:
        img, atlas = atlas_image(insp)
        image_b64, atlas_b64 = _b64(img), _b64(atlas)

    rows = []
    for r in data["regions"]:
        t = kb.get(r["treatment_id"]) if r["treatment_id"] else None
        rows.append({**r, "treatment": t.to_dict() if t else None})

    audit_rows = [
        serialize(e)
        for e in db.scalars(
            select(AuditEntry).where(AuditEntry.inspection_id == insp.id).order_by(AuditEntry.at)
        )
    ]
    detector = (insp.analysis or {}).get("detector") or {}
    return _env.get_template("report.html").render(
        insp=data,
        rows=rows,
        audit=audit_rows,
        image_b64=image_b64,
        atlas_b64=atlas_b64,
        detector=detector,
        sufficiency=(insp.analysis or {}).get("sufficiency") or {},
        legend=[(DAMAGE_LABELS_AR[t], DAMAGE_COLORS[t]) for t in DamageType],
        status_ar=STATUS_AR,
        priority_ar=PRIORITY_AR,
        conf_source_ar=CONF_SOURCE_AR,
        insufficient=INSUFFICIENT_INFO_AR,
        warning=PRELIMINARY_WARNING_AR,
        priority_rules=PRIORITY_RULES_AR,
        is_approved=insp.status == "approved",
        field_needed=[r for r in data["regions"] if r["needs_field_inspection"]],
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        approved_status=RegionStatus.APPROVED.value,
    )
