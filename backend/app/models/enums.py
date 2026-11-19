"""Shared vocabularies: damage types, fixed atlas colors, and review statuses."""
from __future__ import annotations

from enum import Enum


class DamageType(str, Enum):
    CRACK = "crack"
    PLASTER_LOSS = "plaster_loss"  # تساقط أو تقشر الطلاء
    MOISTURE_EROSION = "moisture_erosion"
    MATERIAL_LOSS = "material_loss"  # فقدان أجزاء / تآكل بنيوي
    EDGE_EROSION = "edge_erosion"
    UNCERTAIN = "uncertain"


# Fixed atlas colors (hex). Edge erosion shares the purple "material loss /
# structural" family as specified; it is drawn with a dashed outline.
DAMAGE_COLORS: dict[DamageType, str] = {
    DamageType.CRACK: "#D32F2F",
    DamageType.PLASTER_LOSS: "#F57C00",
    DamageType.MOISTURE_EROSION: "#1E63B5",
    DamageType.MATERIAL_LOSS: "#7B1FA2",
    DamageType.EDGE_EROSION: "#7B1FA2",
    DamageType.UNCERTAIN: "#8A8A8A",
}

DAMAGE_LABELS_AR: dict[DamageType, str] = {
    DamageType.CRACK: "تشقق",
    DamageType.PLASTER_LOSS: "تساقط أو تقشر الطلاء",
    DamageType.MOISTURE_EROSION: "تآكل رطوبي",
    DamageType.MATERIAL_LOSS: "فقدان أجزاء / تآكل بنيوي",
    DamageType.EDGE_EROSION: "تآكل الحواف",
    DamageType.UNCERTAIN: "تلف غير مؤكد / يحتاج فحصًا",
}


class RegionStatus(str, Enum):
    AGENT = "agent"  # نتيجة الوكيل، لم يلمسها المختص
    EDITED = "edited"  # عدّلها المختص
    APPROVED = "approved"  # معتمدة
    NEEDS_REVIEW = "needs_review"  # أعيدت للمراجعة
    REJECTED = "rejected"  # حذفها المختص (حذف منطقي للحفاظ على السجل)


REGION_STATUS_AR: dict[RegionStatus, str] = {
    RegionStatus.AGENT: "نتيجة الوكيل",
    RegionStatus.EDITED: "عدّلها المختص",
    RegionStatus.APPROVED: "معتمدة",
    RegionStatus.NEEDS_REVIEW: "تحتاج مراجعة",
    RegionStatus.REJECTED: "محذوفة",
}


class RegionSource(str, Enum):
    AGENT = "agent"
    EXPERT = "expert"  # أضافها المختص يدويًا


class ConfidenceSource(str, Enum):
    """Where a confidence number comes from. Only 'model' after real evaluation
    would carry a validated meaning; the others are explicitly uncalibrated."""

    MOCK = "mock"
    HEURISTIC = "heuristic_uncalibrated"
    MODEL = "model_unvalidated"
    EXPERT = "expert"


class InspectionStatus(str, Enum):
    REJECTED_QUALITY = "rejected_quality"  # يُطلب إعادة التصوير
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    RETURNED = "returned"  # أعيدت للمراجعة


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


INSUFFICIENT_INFO_AR = (
    "المعلومات غير كافية لتحديد السبب، ويُنصح بإجراء فحص إضافي أو مراجعة مختص."
)
PRELIMINARY_WARNING_AR = "توصية أولية تجريبية، ولا تُنفذ قبل اعتماد مختص الترميم."
