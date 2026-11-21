"""Provisional, transparent rules for priority, low-confidence flags and image
sufficiency. These are placeholders to be replaced by criteria agreed with
conservators; they are documented in the UI so nobody mistakes them for an
official assessment method."""
from __future__ import annotations

from app.models.enums import DamageType, Priority

PRIORITY_RULES_AR = [
    "عالية: فقدان أجزاء أو تآكل حواف تتجاوز مساحته 2% من الصورة، أو تشقق يتجاوز طوله 25% من قطر الصورة.",
    "متوسطة: باقي التلف المؤكد، وكل تلف غير مؤكد (لأنه يحتاج فحصًا).",
    "منخفضة: مناطق صغيرة جدًا (أقل من 0.2% من الصورة) من تقشر أو رطوبة.",
    "هذه قواعد مؤقتة للنموذج الأولي ويجب أن يعتمدها مختص الترميم.",
]


def priority_for(damage_type: str, area_fraction: float, evidence: dict | None = None) -> Priority:
    evidence = evidence or {}
    dt = DamageType(damage_type)
    if dt in (DamageType.MATERIAL_LOSS, DamageType.EDGE_EROSION) and area_fraction > 0.02:
        return Priority.HIGH
    if dt == DamageType.CRACK and evidence.get("length_frac", 0) > 0.25:
        return Priority.HIGH
    if dt in (DamageType.PLASTER_LOSS, DamageType.MOISTURE_EROSION) and area_fraction < 0.002:
        return Priority.LOW
    return Priority.MEDIUM


def needs_field_inspection(damage_type: str, confidence: float, threshold: float) -> bool:
    return damage_type == DamageType.UNCERTAIN.value or confidence < threshold


def assess_sufficiency(quality: dict, detections: list[dict], threshold: float, detector_kind: str) -> dict:
    reasons = []
    if any("وضوح" in w for w in quality.get("warnings", [])):
        reasons.append("وضوح الصورة متوسط وقد تفوت التشققات الدقيقة.")
    low = [d for d in detections if d["confidence"] < threshold]
    if detections and len(low) == len(detections):
        reasons.append("جميع النتائج منخفضة الثقة.")
    if any(d["damage_type"] == DamageType.UNCERTAIN.value for d in detections):
        reasons.append("توجد مناطق لا يمكن تحديد سببها من الصورة وحدها.")
    if not detections:
        reasons.append(
            "لم يُكتشف تلف آليًا. هذا لا يعني خلو الجدار من التلف؛ الكاشف الحالي محدود."
        )
    # "Sufficient" judges the IMAGE. The detector limitation is reported
    # separately so it never makes an image look worse than it is.
    sufficient = not reasons
    if detector_kind != "model":
        reasons.append("الكاشف المستخدم ليس نموذجًا مدربًا على جدران الطريف.")
    return {
        "sufficient": sufficient,
        "reasons_ar": reasons,
        "recommendation_ar": (
            "يُنصح بمراجعة المختص، وبتصوير إضافي قريب للمناطق المعلّمة أو فحص ميداني."
            if not sufficient
            else "الصورة كافية للتحليل الأولي، والنتائج تحتاج اعتماد المختص."
        ),
    }


def materials_by_location(regions: list[dict]) -> list[dict]:
    """Step 6 output (challenge brief): one row per material/tool with the damage
    regions (and grid cells) where it is used. Rejected regions are skipped."""
    rows: dict[tuple[str, str], dict] = {}
    for r in regions:
        if r.get("status") == "rejected":
            continue
        for kind, items in (("material", r.get("materials") or []), ("tool", r.get("tools") or [])):
            for name in items:
                row = rows.setdefault((kind, name), {"kind": kind, "name": name, "regions": [], "cells": []})
                row["regions"].append(f"R{r['index']}")
                for c in r.get("grid_cells") or []:
                    if c not in row["cells"]:
                        row["cells"].append(c)
    return sorted(rows.values(), key=lambda x: (x["kind"] != "material", x["name"]))
