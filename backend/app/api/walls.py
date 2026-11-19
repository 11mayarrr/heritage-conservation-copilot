from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.database.models import Wall
from app.database.session import get_db
from app.models.schemas import WallCreate
from app.services import audit

router = APIRouter(prefix="/api/walls", tags=["walls"])


def wall_out(w: Wall) -> dict:
    return {
        "id": w.id, "code": w.code, "building_name": w.building_name,
        "location_note": w.location_note, "created_at": w.created_at.isoformat(),
        "inspection_count": len(w.inspections),
        "inspections": [
            {"id": i.id, "case_number": i.case_number, "status": i.status,
             "captured_at": i.captured_at.isoformat(), "has_image": i.image_key is not None}
            for i in w.inspections
        ],
    }


@router.get("")
def list_walls(db: Session = Depends(get_db)):
    return [wall_out(w) for w in db.scalars(select(Wall).order_by(Wall.code))]


@router.post("", status_code=201)
def create_wall(body: WallCreate, db: Session = Depends(get_db), user: str = Depends(current_user)):
    w = Wall(code=body.code.strip(), building_name=body.building_name, location_note=body.location_note)
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
