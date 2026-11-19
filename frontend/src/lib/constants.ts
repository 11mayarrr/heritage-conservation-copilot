import type { DamageType, InspectionStatus, Priority, RegionStatus } from "../api/types";

/** Fixed atlas colors. Must match backend/app/models/enums.py DAMAGE_COLORS. */
export const DAMAGE: Record<DamageType, { label: string; color: string; dashed?: boolean }> = {
  crack: { label: "تشقق", color: "#D32F2F" },
  plaster_loss: { label: "تساقط أو تقشر الطلاء", color: "#F57C00" },
  moisture_erosion: { label: "تآكل رطوبي", color: "#1E63B5" },
  material_loss: { label: "فقدان أجزاء / تآكل بنيوي", color: "#7B1FA2" },
  edge_erosion: { label: "تآكل الحواف", color: "#7B1FA2", dashed: true },
  uncertain: { label: "تلف غير مؤكد / يحتاج فحصًا", color: "#8A8A8A", dashed: true },
};

export const DAMAGE_TYPES = Object.keys(DAMAGE) as DamageType[];

export const REGION_STATUS: Record<RegionStatus, { label: string; tone: string }> = {
  agent: { label: "نتيجة الوكيل", tone: "agent" },
  edited: { label: "عدّلها المختص", tone: "edited" },
  approved: { label: "معتمدة", tone: "approved" },
  needs_review: { label: "تحتاج مراجعة", tone: "review" },
  rejected: { label: "محذوفة", tone: "muted" },
};

export const INSPECTION_STATUS: Record<InspectionStatus, { label: string; tone: string }> = {
  rejected_quality: { label: "مرفوضة: يُطلب إعادة التصوير", tone: "danger" },
  in_review: { label: "قيد المراجعة", tone: "agent" },
  approved: { label: "معتمدة", tone: "approved" },
  returned: { label: "أعيدت للمراجعة", tone: "review" },
};

export const PRIORITY: Record<Priority, string> = { high: "عالية", medium: "متوسطة", low: "منخفضة" };

export const CONFIDENCE_SOURCE: Record<string, string> = {
  mock: "وهمية للعرض",
  heuristic_uncalibrated: "تقديرية غير معايرة",
  model_unvalidated: "نموذج غير مُقيّم",
  expert: "حددها المختص",
};

export const ACTION_LABEL: Record<string, string> = {
  create: "إنشاء",
  update: "تعديل",
  delete: "حذف",
  approve: "اعتماد",
  return: "إعادة للمراجعة",
  status: "تغيير الحالة",
  reanalyze: "إعادة تحليل",
  approval_revoked: "إلغاء الاعتماد",
  manual_blur: "إخفاء يدوي",
};

export const FIELD_LABEL: Record<string, string> = {
  damage_type: "نوع التلف",
  polygon: "حدود المنطقة",
  confidence: "درجة الثقة",
  note: "ملاحظة",
  description: "الوصف",
  priority: "الأولوية",
  needs_field_inspection: "فحص ميداني",
  treatment_id: "المعالجة",
  materials: "المواد",
  tools: "الأدوات",
  status: "الحالة",
  expert_notes: "ملاحظات المختص",
};

export const LOW_CONFIDENCE = 0.5;
export const INSUFFICIENT_AR = "المعلومات غير كافية لتحديد السبب، ويُنصح بإجراء فحص إضافي أو مراجعة مختص.";
