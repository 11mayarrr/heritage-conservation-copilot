from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.database.models import Comparison, Inspection
from app.database.session import get_db
from app.models.schemas import ComparisonCreate
from app.services import audit
from app.services.comparisons import comparison_out, create_comparison
from app.services.inspections import InvalidState
from app.services.storage import get_storage

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])


@router.get("")
def list_comparisons(wall_id: str | None = None, db: Session = Depends(get_db)):
    q = select(Comparison).order_by(Comparison.created_at.desc())
    if wall_id:
        q = q.where(Comparison.wall_id == wall_id)
    return [comparison_out(c) for c in db.scalars(q)]


@router.post("", status_code=201)
def compare(body: ComparisonCreate, db: Session = Depends(get_db), user: str = Depends(current_user)):
    before, after = db.get(Inspection, body.before_id), db.get(Inspection, body.after_id)
    if not before or not after:
        raise HTTPException(404, "الحالة غير موجودة.")
    try:
        comp = create_comparison(db, before, after)
    except InvalidState as e:
        raise HTTPException(409, str(e))
    audit.record(db, user=user, entity="comparison", entity_id=comp.id, action="create",
                 new={"before": comp.before_id, "after": comp.after_id})
    db.commit()
    return comparison_out(comp)


@router.get("/{comparison_id}")
def get_comparison(comparison_id: str, db: Session = Depends(get_db)):
    c = db.get(Comparison, comparison_id)
    if not c:
        raise HTTPException(404, "المقارنة غير موجودة.")
    return comparison_out(c)


@router.get("/{comparison_id}/{name}.jpg")
def comparison_image(comparison_id: str, name: str, db: Session = Depends(get_db)):
    if name not in ("side_by_side", "after_aligned"):
        raise HTTPException(404)
    if not db.get(Comparison, comparison_id):
        raise HTTPException(404)
    key = f"comparisons/{comparison_id}/{name}.jpg"
    st = get_storage()
    if not st.exists(key):
        raise HTTPException(404, "الصورة غير متاحة (المحاذاة غير موثوقة).")
    return Response(st.get(key), media_type="image/jpeg")
