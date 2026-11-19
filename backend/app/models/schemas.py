"""API request/response schemas (Pydantic structured outputs)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import DamageType, Priority, RegionStatus


class WallCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    building_name: str = ""
    location_note: str = ""


class WallOut(BaseModel):
    id: str
    code: str
    building_name: str
    location_note: str
    created_at: datetime
    inspection_count: int = 0


class RegionOut(BaseModel):
    id: str
    index: int
    damage_type: DamageType
    damage_label_ar: str
    color: str
    polygon: list[list[float]]
    confidence: float
    confidence_source: str
    low_confidence: bool
    area_fraction: float
    grid_cells: list[str]
    description: str
    priority: Priority
    status: RegionStatus
    status_label_ar: str
    source: str
    needs_field_inspection: bool
    note: str
    treatment_id: str | None
    materials: list[str]
    tools: list[str]
    updated_at: datetime


class RegionCreate(BaseModel):
    damage_type: DamageType
    polygon: list[list[float]]
    confidence: float = Field(default=1.0, ge=0, le=1)
    description: str = ""
    note: str = ""
    priority: Priority = Priority.MEDIUM
    reason: str = ""


class RegionUpdate(BaseModel):
    damage_type: DamageType | None = None
    polygon: list[list[float]] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    description: str | None = None
    note: str | None = None
    priority: Priority | None = None
    needs_field_inspection: bool | None = None
    treatment_id: str | None = None
    materials: list[str] | None = None
    tools: list[str] | None = None
    reason: str = ""

    @field_validator("polygon")
    @classmethod
    def _poly(cls, v):
        if v is not None and len(v) < 3:
            raise ValueError("polygon needs at least 3 points")
        return v


class ReviewAction(BaseModel):
    reason: str = ""


class InspectionNotes(BaseModel):
    expert_notes: str
    reason: str = ""


class ManualBlur(BaseModel):
    boxes: list[list[float]]  # normalized x, y, w, h
    reason: str = ""


class ComparisonCreate(BaseModel):
    before_id: str
    after_id: str


class SegmentRequest(BaseModel):
    points: list[list[float]] = Field(default_factory=list)  # [[x, y, 1|0], ...] normalized
    box: list[float] | None = None  # [x0, y0, x1, y1] normalized
