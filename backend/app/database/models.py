"""ORM tables. Geometry is stored as normalized polygon points (0..1) so it is
independent of image resolution."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Wall(Base):
    __tablename__ = "walls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # رقم الجدار
    building_name: Mapped[str] = mapped_column(String(200), default="")
    location_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    inspections: Mapped[list[Inspection]] = relationship(
        back_populates="wall", order_by="Inspection.captured_at"
    )


class Inspection(Base):
    """One photo of one wall, at one point in time: a case (حالة)."""

    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    wall_id: Mapped[str] = mapped_column(ForeignKey("walls.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_by: Mapped[str] = mapped_column(String(120), default="")

    status: Mapped[str] = mapped_column(String(32))
    image_key: Mapped[str | None] = mapped_column(String(300), nullable=True)  # anonymized
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)

    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    privacy: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)  # detector info, sufficiency
    grid: Mapped[dict] = mapped_column(JSON, default=dict)

    expert_notes: Mapped[str] = mapped_column(Text, default="")
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    wall: Mapped[Wall] = relationship(back_populates="inspections")
    regions: Mapped[list[Region]] = relationship(
        back_populates="inspection", order_by="Region.index", cascade="all, delete-orphan"
    )


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)  # human-friendly number, R1, R2...

    damage_type: Mapped[str] = mapped_column(String(32))
    polygon: Mapped[list] = mapped_column(JSON)  # [[x, y], ...] normalized 0..1
    confidence: Mapped[float] = mapped_column(Float)
    confidence_source: Mapped[str] = mapped_column(String(32))
    area_fraction: Mapped[float] = mapped_column(Float, default=0.0)
    grid_cells: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(16), default="medium")

    status: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    needs_field_inspection: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str] = mapped_column(Text, default="")

    treatment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    materials: Mapped[list] = mapped_column(JSON, default=list)
    tools: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    inspection: Mapped[Inspection] = relationship(back_populates="regions")


class AuditEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    user: Mapped[str] = mapped_column(String(120))
    entity: Mapped[str] = mapped_column(String(32))  # inspection | region | wall
    entity_id: Mapped[str] = mapped_column(String(32), index=True)
    inspection_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(32))  # create | update | delete | approve ...
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    old_value: Mapped[object] = mapped_column(JSON, nullable=True)
    new_value: Mapped[object] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    wall_id: Mapped[str] = mapped_column(ForeignKey("walls.id"), index=True)
    before_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"))
    after_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
