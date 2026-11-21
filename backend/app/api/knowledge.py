from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.models.enums import DAMAGE_COLORS, DAMAGE_LABELS_AR, DamageType
from app.rag.knowledge_base import get_kb

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("")
def list_treatments():
    kb = get_kb()
    return {"treatments": [e.to_dict() for e in kb.entries], "sources": kb.sources_index}


@router.get("/retrieve")
def retrieve(damage_type: DamageType, context: str = Query(default="", max_length=2000)):
    return get_kb().retrieve(damage_type.value, context)


@router.get("/damage-types")
def damage_types():
    return [{"id": t.value, "label_ar": DAMAGE_LABELS_AR[t], "color": DAMAGE_COLORS[t]} for t in DamageType]


@router.get("/glossary")
def glossary():
    """Damage glossary (an input in the challenge action map). Draft until replaced
    by the conservation authority's approved glossary."""
    path = Path(get_settings().knowledge_base_dir) / "damage_glossary.json"
    if not path.exists():
        return {"status": "missing", "note_ar": "لا يوجد مسرد تلف بعد.", "terms": []}
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/{treatment_id}")
def get_treatment(treatment_id: str):
    t = get_kb().get(treatment_id)
    if not t:
        raise HTTPException(404, "المعالجة غير موجودة.")
    return t.to_dict()
