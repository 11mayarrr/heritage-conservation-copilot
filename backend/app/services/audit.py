from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import AuditEntry


def record(
    db: Session,
    *,
    user: str,
    entity: str,
    entity_id: str,
    action: str,
    inspection_id: str | None = None,
    field: str | None = None,
    old=None,
    new=None,
    reason: str = "",
) -> AuditEntry:
    entry = AuditEntry(
        user=user,
        entity=entity,
        entity_id=entity_id,
        inspection_id=inspection_id,
        action=action,
        field=field,
        old_value=old,
        new_value=new,
        reason=reason or "",
    )
    db.add(entry)
    return entry


def serialize(e: AuditEntry) -> dict:
    return {
        "id": e.id,
        "at": e.at.isoformat() if e.at else None,
        "user": e.user,
        "entity": e.entity,
        "entity_id": e.entity_id,
        "inspection_id": e.inspection_id,
        "action": e.action,
        "field": e.field,
        "old_value": e.old_value,
        "new_value": e.new_value,
        "reason": e.reason,
    }
