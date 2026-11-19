export type DamageType =
  | "crack"
  | "plaster_loss"
  | "moisture_erosion"
  | "material_loss"
  | "edge_erosion"
  | "uncertain";

export type RegionStatus = "agent" | "edited" | "approved" | "needs_review" | "rejected";
export type InspectionStatus = "rejected_quality" | "in_review" | "approved" | "returned";
export type Priority = "high" | "medium" | "low";
export type Point = [number, number];

export interface Region {
  id: string;
  index: number;
  damage_type: DamageType;
  damage_label_ar: string;
  color: string;
  polygon: Point[];
  confidence: number;
  confidence_source: string;
  low_confidence: boolean;
  area_fraction: number;
  grid_cells: string[];
  description: string;
  priority: Priority;
  status: RegionStatus;
  status_label_ar: string;
  source: "agent" | "expert";
  needs_field_inspection: boolean;
  note: string;
  treatment_id: string | null;
  materials: string[];
  tools: string[];
  updated_at: string | null;
}

export interface DetectorInfo {
  name: string;
  kind: "mock" | "heuristic" | "model";
  version: string;
  validated: boolean;
  disclaimer: string;
}

export interface Inspection {
  id: string;
  case_number: string;
  wall: { id: string; code: string; building_name: string };
  captured_at: string;
  created_at: string;
  created_by: string;
  status: InspectionStatus;
  width: number;
  height: number;
  has_image: boolean;
  quality: {
    acceptable: boolean;
    sharpness: number;
    brightness: number;
    contrast: number;
    issues: string[];
    warnings: string[];
  };
  privacy: { faces_hidden?: number; detector?: string; method?: string; notice?: string; manual_boxes?: number };
  analysis?: {
    detector?: DetectorInfo;
    sufficiency?: { sufficient: boolean; reasons_ar: string[]; recommendation_ar: string };
    trace?: string[];
  };
  grid: { cols: number; rows: number; type: string };
  expert_notes: string;
  approved_by: string | null;
  approved_at: string | null;
  regions: Region[];
  summary: {
    total: number;
    by_type: Record<string, { count: number; area_fraction: number }>;
    low_confidence: number;
    field_inspection: number;
    approved: number;
    edited: number;
    agent: number;
    needs_review: number;
  };
}

export interface WallSummary {
  id: string;
  code: string;
  building_name: string;
  location_note: string;
  created_at: string;
  inspection_count: number;
  inspections: { id: string; case_number: string; status: InspectionStatus; captured_at: string; has_image: boolean }[];
}

export interface Source {
  title: string;
  publisher: string;
  year: string;
  locator: string;
  url: string;
  quote: string;
}

export interface Treatment {
  id: string;
  damage_types: DamageType[];
  title_ar: string;
  method_ar: string;
  usage_ar: string;
  materials: string[];
  tools: string[];
  cautions_ar: string[];
  sources: Source[];
  approval: "approved" | "demo_unapproved";
  approval_label_ar: string;
  suitability?: "high" | "medium" | "low";
  suitability_ar?: string;
}

export interface Retrieval {
  damage_type: DamageType;
  results: Treatment[];
  sufficient: boolean;
  message_ar: string;
  warning_ar: string;
}

export interface KnowledgeSource {
  id: string;
  title: string;
  publisher: string;
  year: string;
  url: string;
  status: "read" | "not_read";
  context_note_ar: string;
  authors?: string;
  license?: string;
}

export interface AuditEntry {
  id: number;
  at: string;
  user: string;
  entity: string;
  entity_id: string;
  inspection_id: string | null;
  action: string;
  field: string | null;
  old_value: unknown;
  new_value: unknown;
  reason: string;
}

export interface ComparisonItem {
  after_region_id: string | null;
  after_index: number | null;
  before_region_id: string | null;
  before_index: number | null;
  damage_type: DamageType;
  status: "new" | "grew" | "unchanged" | "not_found";
  status_ar: string;
  iou: number;
  area_change: number | null;
  polygon_in_before: Point[];
}

export interface Comparison {
  id: string;
  wall_id: string;
  before_id: string;
  after_id: string;
  created_at: string;
  registration: { ok: boolean; matches: number; inliers: number; inlier_ratio: number; message_ar: string };
  regions: { items: ComparisonItem[]; summary: Record<string, number>; reliable: boolean };
  visual_candidates: { available: boolean; reason_ar: string; candidates: { polygon: Point[]; confidence: number }[] };
  aligned_key: string | null;
  before: { id: string; case_number: string; captured_at: string };
  after: { id: string; case_number: string; captured_at: string };
  notes_ar: string[];
}

export interface Health {
  status: string;
  detector: DetectorInfo;
  original_images_stored: boolean;
  segmenter: SegmenterInfo;
  segmenter_fallback_reason: string | null;
  privacy_notice_ar: string;
}

export interface SegmenterInfo {
  name: string;
  kind: "sam2" | "grabcut";
  description_ar: string;
}

export interface SegmentPreview {
  polygon: Point[] | null;
  area_fraction?: number;
  other_parts?: number;
  score: number | null;
  segmenter: SegmenterInfo;
  message_ar: string;
}
