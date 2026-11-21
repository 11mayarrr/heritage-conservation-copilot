"""Inspection lifecycle: run the agent, persist results, expert edits with a
full audit trail, re-analysis, and approval."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.rules import needs_field_inspection, priority_for
from app.agents.workflow import run_inspection
from app.config import get_settings
from app.database.models import Inspection, Region, Wall
from app.models.enums import (
    DAMAGE_COLORS,
    DAMAGE_LABELS_AR,
    REGION_STATUS_AR,
    ConfidenceSource,
    DamageType,
    InspectionStatus,
    RegionSource,
    RegionStatus,
)
from app.privacy.anonymizer import apply_manual_boxes
from app.rag.knowledge_base import get_kb
from app.services import audit
from app.services.storage import get_storage
from app.agents.rules import materials_by_location
from app.services import grids
from app.vision.geometry import grid_cells, polygon_area, validate_polygon
from app.vision.imageio import decode_image, encode_jpeg


class NotFound(LookupError):
    pass


class InvalidState(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def next_case_number(db: Session) -> str:
    year = _now().year
    count = db.scalar(select(func.count(Inspection.id))) or 0
    return f"HCC-{year}-{count + 1:04d}"


def get_or_404(db: Session, model, obj_id: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise NotFound(f"{model.__name__} {obj_id} not found")
    return obj


def _default_treatment(damage_type: str, description: str) -> tuple[str | None, list[str], list[str]]:
    res = get_kb().retrieve(damage_type, description, k=1)
    if not res["results"]:
        return None, [], []
    top = res["results"][0]
    return top["id"], list(top["materials"]), list(top["tools"])


def create_inspection(
    db: Session, wall: Wall, image_bytes: bytes, user: str, captured_at: datetime | None = None
) -> Inspection:
    img = decode_image(image_bytes)
    state = run_inspection(img, grids.wall_grid(wall))

    insp = Inspection(
        case_number=next_case_number(db),
        wall_id=wall.id,
        captured_at=captured_at or _now(),
        created_by=user,
        status=state["status"],
        width=img.shape[1],
        height=img.shape[0],
        quality=state.get("quality", {}),
        privacy=state.get("privacy", {}),
        grid=state.get("grid") or grids.wall_grid(wall),
        analysis={
            "detector": state.get("detector"),
            "sufficiency": state.get("sufficiency"),
            "trace": state.get("trace", []),
            # Frozen copy of what the agent proposed, so the system can later be
            # evaluated against the expert-approved result (scripts/evaluate.py).
            "agent_detections": [
                {k: d[k] for k in ("damage_type", "polygon", "confidence", "confidence_source")}
                for d in state.get("detections", [])
            ],
        },
    )
    db.add(insp)
    db.flush()

    if state["status"] != InspectionStatus.REJECTED_QUALITY.value:
        key = f"inspections/{insp.id}/anonymized.jpg"
        get_storage().put(key, encode_jpeg(state["anonymized"]))
        insp.image_key = key
        for i, d in enumerate(state.get("detections", []), start=1):
            tid, mats, tools = _default_treatment(d["damage_type"], d["description"])
            db.add(
                Region(
                    inspection_id=insp.id,
                    index=i,
                    damage_type=d["damage_type"],
                    polygon=d["polygon"],
                    confidence=d["confidence"],
                    confidence_source=d["confidence_source"],
                    area_fraction=d["area_fraction"],
                    grid_cells=d["grid_cells"],
                    description=d["description"],
                    priority=d["priority"],
                    status=RegionStatus.AGENT.value,
                    source=RegionSource.AGENT.value,
                    needs_field_inspection=d["needs_field_inspection"],
                    treatment_id=tid,
                    materials=mats,
                    tools=tools,
                )
            )
    audit.record(
        db, user=user, entity="inspection", entity_id=insp.id, inspection_id=insp.id,
        action="create", new={"status": insp.status, "case_number": insp.case_number},
    )
    db.commit()
    db.refresh(insp)
    return insp


# --------------------------------------------------------------------- serialize
def region_out(r: Region, grid: dict | None = None) -> dict:
    s = get_settings()
    dt = DamageType(r.damage_type)
    return {
        "id": r.id,
        "index": r.index,
        "damage_type": dt.value,
        "damage_label_ar": DAMAGE_LABELS_AR[dt],
        "color": DAMAGE_COLORS[dt],
        "polygon": r.polygon,
        "confidence": r.confidence,
        "confidence_source": r.confidence_source,
        "low_confidence": r.confidence < s.low_confidence_threshold,
        "area_fraction": r.area_fraction,
        # Estimated m^2, only when the wall grid has real dimensions.
        "area_m2": grids.area_m2(r.area_fraction, grid if grid is not None else r.inspection.grid),
        "grid_cells": r.grid_cells,
        "description": r.description,
        "priority": r.priority,
        "status": r.status,
        "status_label_ar": REGION_STATUS_AR[RegionStatus(r.status)],
        "source": r.source,
        "needs_field_inspection": r.needs_field_inspection,
        "note": r.note,
        "treatment_id": r.treatment_id,
        "materials": r.materials,
        "tools": r.tools,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def inspection_out(insp: Inspection, include_rejected: bool = False) -> dict:
    regions = [r for r in insp.regions if include_rejected or r.status != RegionStatus.REJECTED.value]
    return {
        "id": insp.id,
        "case_number": insp.case_number,
        "wall": {"id": insp.wall.id, "code": insp.wall.code, "building_name": insp.wall.building_name,
                 "grid": grids.wall_grid(insp.wall)},
        "captured_at": insp.captured_at.isoformat() if insp.captured_at else None,
        "created_at": insp.created_at.isoformat() if insp.created_at else None,
        "created_by": insp.created_by,
        "status": insp.status,
        "width": insp.width,
        "height": insp.height,
        "has_image": insp.image_key is not None,
        "quality": insp.quality,
        "privacy": insp.privacy,
        "analysis": insp.analysis,
        "grid": insp.grid,
        "expert_notes": insp.expert_notes,
        "approved_by": insp.approved_by,
        "approved_at": insp.approved_at.isoformat() if insp.approved_at else None,
        "regions": (regs := [region_out(r, insp.grid) for r in regions]),
        # Step 6 of the action map: each material/tool with the regions and grid cells it is used in.
        "materials_by_location": materials_by_location(regs),
        "summary": summarize(regions),
    }


def summarize(regions: list[Region]) -> dict:
    s = get_settings()
    by_type: dict[str, dict] = {}
    for r in regions:
        t = by_type.setdefault(r.damage_type, {"count": 0, "area_fraction": 0.0})
        t["count"] += 1
        t["area_fraction"] = round(t["area_fraction"] + r.area_fraction, 5)
    return {
        "total": len(regions),
        "by_type": by_type,
        "low_confidence": sum(1 for r in regions if r.confidence < s.low_confidence_threshold),
        "field_inspection": sum(1 for r in regions if r.needs_field_inspection),
        "approved": sum(1 for r in regions if r.status == RegionStatus.APPROVED.value),
        "edited": sum(1 for r in regions if r.status == RegionStatus.EDITED.value),
        "agent": sum(1 for r in regions if r.status == RegionStatus.AGENT.value),
        "needs_review": sum(1 for r in regions if r.status == RegionStatus.NEEDS_REVIEW.value),
    }


# ----------------------------------------------------------------- expert edits
def _ensure_editable(insp: Inspection) -> None:
    if insp.status == InspectionStatus.REJECTED_QUALITY.value:
        raise InvalidState("الصورة مرفوضة لجودتها؛ ارفع صورة جديدة.")


def _touch_inspection_after_edit(db: Session, insp: Inspection, user: str) -> None:
    if insp.status == InspectionStatus.APPROVED.value:
        audit.record(db, user=user, entity="inspection", entity_id=insp.id, inspection_id=insp.id,
                     action="approval_revoked", field="status", old=insp.status,
                     new=InspectionStatus.IN_REVIEW.value, reason="تعديل بعد الاعتماد")
        insp.status = InspectionStatus.IN_REVIEW.value
        insp.approved_by = None
        insp.approved_at = None


def add_region(db: Session, insp: Inspection, data: dict, user: str) -> Region:
    _ensure_editable(insp)
    s = get_settings()
    poly = validate_polygon(data["polygon"])
    dt = DamageType(data["damage_type"]).value
    area = polygon_area(poly)
    tid, mats, tools = _default_treatment(dt, data.get("description", ""))
    idx = max((r.index for r in insp.regions), default=0) + 1
    region = Region(
        inspection_id=insp.id,
        index=idx,
        damage_type=dt,
        polygon=poly,
        confidence=data.get("confidence", 1.0),
        confidence_source=ConfidenceSource.EXPERT.value,
        area_fraction=round(area, 5),
        grid_cells=grid_cells(poly, *grids.dims(insp.grid)),
        description=data.get("description", ""),
        priority=data.get("priority", priority_for(dt, area).value),
        status=RegionStatus.EDITED.value,
        source=RegionSource.EXPERT.value,
        needs_field_inspection=dt == DamageType.UNCERTAIN.value,
        note=data.get("note", ""),
        treatment_id=tid,
        materials=mats,
        tools=tools,
    )
    db.add(region)
    db.flush()
    audit.record(db, user=user, entity="region", entity_id=region.id, inspection_id=insp.id,
                 action="create", new=region_out(region), reason=data.get("reason", ""))
    _touch_inspection_after_edit(db, insp, user)
    db.commit()
    db.refresh(region)
    return region


EDITABLE = ["damage_type", "polygon", "confidence", "description", "note", "priority",
            "needs_field_inspection", "treatment_id", "materials", "tools"]


def update_region(db: Session, region: Region, changes: dict, user: str) -> Region:
    insp = region.inspection
    _ensure_editable(insp)
    if region.status == RegionStatus.REJECTED.value:
        raise InvalidState("المنطقة محذوفة.")
    s = get_settings()
    reason = changes.pop("reason", "") or ""
    changed = False
    for field in EDITABLE:
        if field not in changes or changes[field] is None:
            continue
        new = changes[field]
        if field == "polygon":
            new = validate_polygon(new)
        if field == "damage_type":
            new = DamageType(new).value
        if field == "treatment_id" and new and get_kb().get(new) is None:
            raise InvalidState("المعالجة غير موجودة في قاعدة المعرفة.")
        old = getattr(region, field)
        if old == new:
            continue
        audit.record(db, user=user, entity="region", entity_id=region.id, inspection_id=insp.id,
                     action="update", field=field, old=old, new=new, reason=reason)
        setattr(region, field, new)
        changed = True
        if field == "confidence":
            region.confidence_source = ConfidenceSource.EXPERT.value
    if not changed:
        return region

    # Re-analysis of derived fields after an edit (workflow step 14).
    if "polygon" in changes and changes["polygon"] is not None:
        region.area_fraction = round(polygon_area(region.polygon), 5)
        region.grid_cells = grid_cells(region.polygon, *grids.dims(insp.grid))
    if changes.get("damage_type") and "treatment_id" not in changes:
        tid, mats, tools = _default_treatment(region.damage_type, region.description)
        audit.record(db, user="agent", entity="region", entity_id=region.id, inspection_id=insp.id,
                     action="reanalyze", field="treatment_id", old=region.treatment_id, new=tid,
                     reason="إعادة استرجاع المعالجة بعد تغيير نوع التلف")
        region.treatment_id, region.materials, region.tools = tid, mats, tools
        if changes.get("needs_field_inspection") is None:
            region.needs_field_inspection = needs_field_inspection(
                region.damage_type, region.confidence, s.low_confidence_threshold
            ) if region.source == RegionSource.AGENT.value else region.damage_type == DamageType.UNCERTAIN.value

    if region.status != RegionStatus.EDITED.value:
        audit.record(db, user=user, entity="region", entity_id=region.id, inspection_id=insp.id,
                     action="status", field="status", old=region.status, new=RegionStatus.EDITED.value)
        region.status = RegionStatus.EDITED.value
    region.updated_at = _now()
    _touch_inspection_after_edit(db, insp, user)
    db.commit()
    db.refresh(region)
    return region


def delete_region(db: Session, region: Region, user: str, reason: str = "") -> None:
    """Soft delete: kept in the audit log and excluded from maps and reports."""
    insp = region.inspection
    _ensure_editable(insp)
    audit.record(db, user=user, entity="region", entity_id=region.id, inspection_id=insp.id,
                 action="delete", field="status", old=region.status, new=RegionStatus.REJECTED.value,
                 reason=reason)
    region.status = RegionStatus.REJECTED.value
    region.updated_at = _now()
    _touch_inspection_after_edit(db, insp, user)
    db.commit()


def set_region_status(db: Session, region: Region, status: RegionStatus, user: str, reason: str = "") -> Region:
    insp = region.inspection
    _ensure_editable(insp)
    if region.status == RegionStatus.REJECTED.value:
        raise InvalidState("المنطقة محذوفة.")
    if region.status != status.value:
        audit.record(db, user=user, entity="region", entity_id=region.id, inspection_id=insp.id,
                     action="approve" if status == RegionStatus.APPROVED else "return",
                     field="status", old=region.status, new=status.value, reason=reason)
        region.status = status.value
        region.updated_at = _now()
        if status == RegionStatus.NEEDS_REVIEW:
            _touch_inspection_after_edit(db, insp, user)
    db.commit()
    db.refresh(region)
    return region


def update_notes(db: Session, insp: Inspection, notes: str, user: str, reason: str = "") -> Inspection:
    if insp.expert_notes != notes:
        audit.record(db, user=user, entity="inspection", entity_id=insp.id, inspection_id=insp.id,
                     action="update", field="expert_notes", old=insp.expert_notes, new=notes, reason=reason)
        insp.expert_notes = notes
        db.commit()
    return insp


def approve_inspection(db: Session, insp: Inspection, user: str, reason: str = "") -> Inspection:
    _ensure_editable(insp)
    active = [r for r in insp.regions if r.status != RegionStatus.REJECTED.value]
    pending = [r.index for r in active if r.status == RegionStatus.NEEDS_REVIEW.value]
    if pending:
        raise InvalidState(f"توجد مناطق معادة للمراجعة لم تُحسم: {', '.join(f'R{i}' for i in pending)}")
    for r in active:
        if r.status != RegionStatus.APPROVED.value:
            audit.record(db, user=user, entity="region", entity_id=r.id, inspection_id=insp.id,
                         action="approve", field="status", old=r.status, new=RegionStatus.APPROVED.value,
                         reason="ضمن اعتماد الحالة")
            r.status = RegionStatus.APPROVED.value
    audit.record(db, user=user, entity="inspection", entity_id=insp.id, inspection_id=insp.id,
                 action="approve", field="status", old=insp.status, new=InspectionStatus.APPROVED.value,
                 reason=reason)
    insp.status = InspectionStatus.APPROVED.value
    insp.approved_by = user
    insp.approved_at = _now()
    db.commit()
    db.refresh(insp)
    return insp


def return_inspection(db: Session, insp: Inspection, user: str, reason: str = "") -> Inspection:
    _ensure_editable(insp)
    audit.record(db, user=user, entity="inspection", entity_id=insp.id, inspection_id=insp.id,
                 action="return", field="status", old=insp.status, new=InspectionStatus.RETURNED.value,
                 reason=reason)
    insp.status = InspectionStatus.RETURNED.value
    insp.approved_by = None
    insp.approved_at = None
    for r in insp.regions:
        if r.status == RegionStatus.APPROVED.value:
            r.status = RegionStatus.NEEDS_REVIEW.value
    db.commit()
    db.refresh(insp)
    return insp


def reanalyze(db: Session, insp: Inspection, user: str) -> Inspection:
    """Recompute derived values (area, grid cells, priority suggestions, missing
    treatment links) for all active regions without overwriting expert input."""
    _ensure_editable(insp)
    s = get_settings()
    for r in insp.regions:
        if r.status == RegionStatus.REJECTED.value:
            continue
        r.area_fraction = round(polygon_area(r.polygon), 5)
        r.grid_cells = grid_cells(r.polygon, *grids.dims(insp.grid))
        if not r.treatment_id:
            tid, mats, tools = _default_treatment(r.damage_type, r.description)
            if tid:
                r.treatment_id, r.materials, r.tools = tid, mats, tools
    audit.record(db, user=user, entity="inspection", entity_id=insp.id, inspection_id=insp.id,
                 action="reanalyze", reason="إعادة حساب المساحات والمواقع والمعالجات الناقصة")
    db.commit()
    db.refresh(insp)
    return insp


def apply_manual_blur(db: Session, insp: Inspection, boxes: list[list[float]], user: str, reason: str = "") -> Inspection:
    if not insp.image_key:
        raise InvalidState("لا توجد صورة محفوظة لهذه الحالة.")
    st = get_storage()
    img = decode_image(st.get(insp.image_key))
    img = apply_manual_boxes(img, boxes, get_settings().face_method)
    st.put(insp.image_key, encode_jpeg(img))
    privacy = dict(insp.privacy or {})
    privacy["manual_boxes"] = privacy.get("manual_boxes", 0) + len(boxes)
    insp.privacy = privacy
    audit.record(db, user=user, entity="inspection", entity_id=insp.id, inspection_id=insp.id,
                 action="manual_blur", new={"boxes": len(boxes)}, reason=reason)
    db.commit()
    return insp


def apply_grid(db: Session, insp: Inspection, grid: dict, user: str, reason: str = "") -> bool:
    """Re-map an inspection onto a new wall grid (grid cells only; polygons,
    types and expert input are untouched). Approved inspections are skipped:
    their documented locations stay as approved. Returns True if applied."""
    if insp.status in (InspectionStatus.APPROVED.value, InspectionStatus.REJECTED_QUALITY.value):
        return False
    old = dict(insp.grid or {})
    insp.grid = dict(grid)
    cols, rows = grids.dims(grid)
    for r in insp.regions:
        if r.status != RegionStatus.REJECTED.value:
            r.grid_cells = grid_cells(r.polygon, cols, rows)
    audit.record(db, user=user, entity="inspection", entity_id=insp.id, inspection_id=insp.id,
                 action="update", field="grid", old=old, new=dict(grid),
                 reason=reason or "تطبيق الشبكة المرجعية الجديدة للجدار")
    return True
