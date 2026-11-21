import type { DamageType, InspectionStatus, Region, RegionStatus } from "../api/types";
import { CONFIDENCE_SOURCE, DAMAGE, DAMAGE_TYPES, INSPECTION_STATUS, LOW_CONFIDENCE, REGION_STATUS } from "../lib/constants";

export function DamageSwatch({ type }: { type: DamageType }) {
  const d = DAMAGE[type];
  return (
    <span
      className={`swatch${d.dashed ? " dashed" : ""}`}
      style={d.dashed ? { borderColor: d.color } : { background: d.color }}
      aria-hidden
    />
  );
}

export function DamageLabel({ type }: { type: DamageType }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <DamageSwatch type={type} />
      {DAMAGE[type].label}
    </span>
  );
}

export function Legend() {
  return (
    <div className="legend" aria-label="مفتاح الألوان">
      {DAMAGE_TYPES.map((t) => (
        <span key={t}>
          <DamageLabel type={t} />
        </span>
      ))}
    </div>
  );
}

export function RegionStatusBadge({ status }: { status: RegionStatus }) {
  const s = REGION_STATUS[status];
  return <span className={`badge ${s.tone}`}>{s.label}</span>;
}

export function InspectionStatusBadge({ status }: { status: InspectionStatus }) {
  const s = INSPECTION_STATUS[status];
  return <span className={`badge ${s.tone}`}>{s.label}</span>;
}

export function Confidence({ value, source }: { value: number; source: string }) {
  const low = value < LOW_CONFIDENCE;
  const color = low ? "#b3261e" : value < 0.75 ? "#c0744a" : "#5f7f68";
  return (
    <span className="conf" title={CONFIDENCE_SOURCE[source] ?? source}>
      <span className="bar">
        <i style={{ width: `${Math.round(value * 100)}%`, background: color }} />
      </span>
      <b>{Math.round(value * 100)}%</b>
      <small>{CONFIDENCE_SOURCE[source] ?? source}</small>
    </span>
  );
}

/** All flags an expert needs to see at a glance for one region. */
export function RegionFlags({ r }: { r: Region }) {
  return (
    <span className="chips">
      <RegionStatusBadge status={r.status} />
      {r.low_confidence && <span className="badge low">ثقة منخفضة</span>}
      {r.needs_field_inspection && <span className="badge field">يحتاج فحصًا ميدانيًا</span>}
      {r.source === "expert" && <span className="badge edited">أضافها المختص</span>}
    </span>
  );
}
