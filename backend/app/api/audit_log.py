from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import AuditEntry
from app.database.session import get_db
from app.services.audit import serialize

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit(
    inspection_id: str | None = None,
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    q = select(AuditEntry).order_by(AuditEntry.at.desc(), AuditEntry.id.desc()).limit(limit)
    if inspection_id:
        q = q.where(AuditEntry.inspection_id == inspection_id)
    return [serialize(e) for e in db.scalars(q)]
