from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_specialist
from app.database.models import Inspection, Region, Wall
from app.database.session import get_db
from app.models.enums import RegionStatus
from app.models.schemas import InspectionNotes, ManualBlur, RegionCreate, RegionUpdate, ReviewAction, SegmentRequest
from app.reports.generator import atlas_image, build_report
from app.services import inspections as svc
from app.services.storage import get_storage
from app.vision.geometry import mask_to_polygons, polygon_area
from app.vision.imageio import ImageDecodeError, decode_image, encode_png
from app.vision.segmenters import SegmenterUnavailable, get_segmenter, validate_prompts

router = APIRouter(prefix="/api", tags=["inspections"])

MAX_UPLOAD = 25 * 1024 * 1024


def _insp(db: Session, inspection_id: str) -> Inspection:
    insp = db.get(Inspection, inspection_id)
    if not insp:
        raise HTTPException(404, "الحالة غير موجودة.")
    return insp


def _region(db: Session, inspection_id: str, region_id: str) -> Region:
    r = db.get(Region, region_id)
    if not r or r.inspection_id != inspection_id:
        raise HTTPException(404, "المنطقة غير موجودة.")
    return r


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except svc.InvalidState as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/inspections")
def list_inspections(db: Session = Depends(get_db)):
    items = db.scalars(select(Inspection).order_by(Inspection.created_at.desc()))
    out = []
    for i in items:
        d = svc.inspection_out(i)
        d.pop("analysis", None)
        out.append(d)
    return out


@router.post("/inspections", status_code=201)
async def upload_inspection(
    wall_id: str = Form(...),
    image: UploadFile = File(...),
    captured_at: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: str = Depends(current_user),
):
    wall = db.get(Wall, wall_id)
    if not wall:
        raise HTTPException(404, "الجدار غير موجود.")
    data = await image.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "حجم الصورة يتجاوز 25 ميجابايت.")
    when = None
    if captured_at:
        try:
            when = datetime.fromisoformat(captured_at)
        except ValueError:
            raise HTTPException(422, "صيغة تاريخ التصوير غير صحيحة.")
    try:
        insp = svc.create_inspection(db, wall, data, user, when)
    except ImageDecodeError as e:
        raise HTTPException(422, str(e))
    return svc.inspection_out(insp)


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: str, include_rejected: bool = False, db: Session = Depends(get_db)):
    return svc.inspection_out(_insp(db, inspection_id), include_rejected=include_rejected)


@router.get("/inspections/{inspection_id}/image.jpg")
def anonymized_image(inspection_id: str, download: bool = False, db: Session = Depends(get_db)):
    insp = _insp(db, inspection_id)
    if not insp.image_key:
        raise HTTPException(404, "لا توجد صورة مقبولة لهذه الحالة.")
    headers = {"Content-Disposition": f'attachment; filename="{insp.case_number}-anonymized.jpg"'} if download else {}
    return Response(get_storage().get(insp.image_key), media_type="image/jpeg", headers=headers)


@router.get("/inspections/{inspection_id}/atlas.png")
def atlas(inspection_id: str, download: bool = False, legend: bool = True, db: Session = Depends(get_db)):
    insp = _insp(db, inspection_id)
    if not insp.image_key:
        raise HTTPException(404, "لا توجد صورة مقبولة لهذه الحالة.")
    _, img = atlas_image(insp, legend=legend)
    headers = {"Content-Disposition": f'attachment; filename="{insp.case_number}-damage-atlas.png"'} if download else {}
    return Response(encode_png(img), media_type="image/png", headers=headers)


@router.get("/inspections/{inspection_id}/report.html", response_class=HTMLResponse)
def report(inspection_id: str, download: bool = False, db: Session = Depends(get_db)):
    insp = _insp(db, inspection_id)
    html = build_report(db, insp)
    headers = {"Content-Disposition": f'attachment; filename="{insp.case_number}-report.html"'} if download else {}
    return HTMLResponse(html, headers=headers)


@router.put("/inspections/{inspection_id}/notes")
def set_notes(inspection_id: str, body: InspectionNotes, db: Session = Depends(get_db), user: str = Depends(current_user)):
    insp = svc.update_notes(db, _insp(db, inspection_id), body.expert_notes, user, body.reason)
    return svc.inspection_out(insp)


@router.post("/inspections/{inspection_id}/approve")
def approve(inspection_id: str, body: ReviewAction, db: Session = Depends(get_db), user: str = Depends(require_specialist)):
    return svc.inspection_out(_guard(svc.approve_inspection, db, _insp(db, inspection_id), user, body.reason))


@router.post("/inspections/{inspection_id}/return")
def return_for_review(inspection_id: str, body: ReviewAction, db: Session = Depends(get_db), user: str = Depends(current_user)):
    return svc.inspection_out(_guard(svc.return_inspection, db, _insp(db, inspection_id), user, body.reason))


@router.post("/inspections/{inspection_id}/reanalyze")
def reanalyze(inspection_id: str, db: Session = Depends(get_db), user: str = Depends(current_user)):
    return svc.inspection_out(_guard(svc.reanalyze, db, _insp(db, inspection_id), user))


@router.post("/inspections/{inspection_id}/blur")
def manual_blur(inspection_id: str, body: ManualBlur, db: Session = Depends(get_db), user: str = Depends(current_user)):
    return svc.inspection_out(_guard(svc.apply_manual_blur, db, _insp(db, inspection_id), body.boxes, user, body.reason))


@router.post("/inspections/{inspection_id}/segment")
def segment(inspection_id: str, body: SegmentRequest, db: Session = Depends(get_db)):
    """Click-to-segment preview (SAM 2 or GrabCut). Nothing is saved: the expert
    then creates a region or applies the outline to an existing one."""
    insp = _insp(db, inspection_id)
    if not insp.image_key:
        raise HTTPException(404, "لا توجد صورة مقبولة لهذه الحالة.")
    try:
        validate_prompts(body.points, body.box)
        seg = get_segmenter()
    except ValueError as e:
        raise HTTPException(422, str(e))
    except SegmenterUnavailable as e:
        raise HTTPException(503, str(e))
    img = decode_image(get_storage().get(insp.image_key))
    res = seg.segment(img, body.points, body.box, cache_key=insp.image_key)
    polys = mask_to_polygons(res.mask, min_area_px=30, epsilon_frac=0.003)
    if not polys:
        return {"polygon": None, "segmenter": res.info.__dict__, "score": res.score,
                "message_ar": "لم يُعثر على منطقة عند النقاط المحددة. جرّب نقطة أخرى داخل المنطقة."}
    best = max(polys, key=polygon_area)
    return {
        "polygon": best,
        "area_fraction": round(polygon_area(best), 5),
        "other_parts": len(polys) - 1,
        "score": res.score,
        "segmenter": res.info.__dict__,
        "message_ar": "",
    }


# ------------------------------------------------------------------- regions
@router.post("/inspections/{inspection_id}/regions", status_code=201)
def add_region(inspection_id: str, body: RegionCreate, db: Session = Depends(get_db), user: str = Depends(current_user)):
    r = _guard(svc.add_region, db, _insp(db, inspection_id), body.model_dump(mode="json"), user)
    return svc.region_out(r)


@router.patch("/inspections/{inspection_id}/regions/{region_id}")
def update_region(inspection_id: str, region_id: str, body: RegionUpdate, db: Session = Depends(get_db), user: str = Depends(current_user)):
    changes = body.model_dump(mode="json", exclude_unset=True)
    r = _guard(svc.update_region, db, _region(db, inspection_id, region_id), changes, user)
    return svc.region_out(r)


@router.delete("/inspections/{inspection_id}/regions/{region_id}", status_code=204)
def delete_region(inspection_id: str, region_id: str, reason: str = "", db: Session = Depends(get_db), user: str = Depends(current_user)):
    _guard(svc.delete_region, db, _region(db, inspection_id, region_id), user, reason)
    return Response(status_code=204)


@router.post("/inspections/{inspection_id}/regions/{region_id}/approve")
def approve_region(inspection_id: str, region_id: str, body: ReviewAction, db: Session = Depends(get_db), user: str = Depends(require_specialist)):
    r = _guard(svc.set_region_status, db, _region(db, inspection_id, region_id), RegionStatus.APPROVED, user, body.reason)
    return svc.region_out(r)


@router.post("/inspections/{inspection_id}/regions/{region_id}/return")
def return_region(inspection_id: str, region_id: str, body: ReviewAction, db: Session = Depends(get_db), user: str = Depends(current_user)):
    r = _guard(svc.set_region_status, db, _region(db, inspection_id, region_id), RegionStatus.NEEDS_REVIEW, user, body.reason)
    return svc.region_out(r)
