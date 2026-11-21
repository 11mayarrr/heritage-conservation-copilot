import type { InspectionStatus } from "../api/types";

/** Excel and GeoJSON are produced only for inspections a specialist approved. */
export const canExport = (status: InspectionStatus): boolean => status === "approved";

export const EXPORT_BLOCKED_HINT = "يتاح التصدير بعد أن يعتمد المختص الحالة";

export const EXPORT_NOTE =
  "تصدير Excel وGeoJSON متاح للحالات المعتمدة فقط. إحداثيات GeoJSON محلية على صورة الجدار وليست إحداثيات جغرافية حقيقية، وهذا مكتوب داخل الملف.";
