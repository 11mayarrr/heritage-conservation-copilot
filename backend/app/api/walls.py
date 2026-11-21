from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.database.models import Wall
from app.database.session import get_db
from app.models.schemas import WallCreate, WallGridUpdate
from app.services import audit, grids
from app.services import inspections as insp_svc

router = APIRouter(prefix="/api/walls", tags=["walls"])


def wall_out(w: Wall) -> dict:
    g = grids.wall_grid(w)
    return {
        "id": w.id, "code": w.code, "building_name": w.building_name,
        "location_note": w.location_note, "created_at": w.created_at.isoformat(),
        "grid": g,
        "cell_size_m": grids.cell_size_m(g),
        "inspection_count": len(w.inspections),
        "inspections": [
            {"id": i.id, "case_number": i.case_number, "status": i.status,
             "captured_at": i.captured_at.isoformat(), "has_image": i.image_key is not None,
             "grid_version": (i.grid or {}).get("version", 0)}
            for i in w.inspections
        ],
    }


def _grid_or_400(data: dict, version: int) -> dict:
    try:
        return grids.normalize(data, version)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("")
def list_walls(db: Session = Depends(get_db)):
    return [wall_out(w) for w in db.scalars(select(Wall).order_by(Wall.code))]


@router.post("", status_code=201)
def create_wall(body: WallCreate, db: Session = Depends(get_db), user: str = Depends(current_user)):
    grid = _grid_or_400(body.grid.model_dump(), 1) if body.grid else None
    w = Wall(code=body.code.strip(), building_name=body.building_name,
             location_note=body.location_note, grid=grid)
    db.add(w)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "رقم الجدار مستخدم مسبقًا.")
    audit.record(db, user=user, entity="wall", entity_id=w.id, action="create", new=body.model_dump())
    db.commit()
    db.refresh(w)
    return wall_out(w)


@router.get("/{wall_id}")
def get_wall(wall_id: str, db: Session = Depends(get_db)):
    w = db.get(Wall, wall_id)
    if not w:
        raise HTTPException(404, "الجدار غير موجود.")
    return wall_out(w)


@router.put("/{wall_id}/grid")
def set_wall_grid(wall_id: str, body: WallGridUpdate, db: Session = Depends(get_db),
                  user: str = Depends(current_user)):
    """Define or change this wall's reference grid. New inspections use it.
    Existing inspections keep the grid they were analysed with, unless
    apply_to_open is set: then inspections not yet approved are re-mapped."""
    w = db.get(Wall, wall_id)
    if not w:
        raise HTTPException(404, "الجدار غير موجود.")
    old = grids.wall_grid(w)
    data = body.model_dump(exclude={"apply_to_open", "reason"})
    new = _grid_or_400(data, (w.grid or {}).get("version", 0) + 1)
    w.grid = new
    audit.record(db, user=user, entity="wall", entity_id=w.id, action="update", field="grid",
                 old=old, new=new, reason=body.reason)
    applied, kept = [], []
    if body.apply_to_open:
        for i in w.inspections:
            (applied if insp_svc.apply_grid(db, i, new, user, body.reason) else kept).append(i.case_number)
    db.commit()
    db.refresh(w)
    return {**wall_out(w), "applied_to": applied, "kept_previous_grid": kept}
