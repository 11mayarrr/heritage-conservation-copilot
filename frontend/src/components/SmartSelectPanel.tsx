import { useState } from "react";
import type { DamageType, Region, SegmentPreview } from "../api/types";
import { DAMAGE, DAMAGE_TYPES } from "../lib/constants";
import { pct } from "../lib/format";

interface Props {
  points: [number, number, number][];
  label: 0 | 1;
  onLabel: (l: 0 | 1) => void;
  preview: SegmentPreview | null;
  busy: boolean;
  error: string | null;
  regions: Region[];
  initialTarget: string | null;
  onUndo: () => void;
  onClear: () => void;
  onSaveNew: (type: DamageType) => void;
  onApply: (regionId: string) => void;
}

/** Side panel for the click-to-segment tool (SAM 2, or GrabCut fallback). */
export function SmartSelectPanel(p: Props) {
  const [type, setType] = useState<DamageType>("plaster_loss");
  const [target, setTarget] = useState(p.initialTarget ?? "");
  const seg = p.preview?.segmenter;
  const active = p.regions.filter((r) => r.status !== "rejected");

  return (
    <div className="card">
      <h2>التحديد الذكي</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        انقر داخل منطقة التلف فيرسم النظام حدودها. أضف نقاطًا أخرى لتحسين النتيجة. الأداة ترسم الحدود فقط، ونوع التلف
        يحدده المختص.
      </p>
      {seg && (
        <div className={`banner ${seg.kind === "sam2" ? "info" : "warn"}`}>
          <b>{seg.kind === "sam2" ? "SAM 2" : "وضع بديل (GrabCut)"}:</b> {seg.description_ar}
        </div>
      )}
      <div className="toolbar" style={{ marginBottom: 8 }}>
        <button className={p.label === 1 ? "ok" : ""} onClick={() => p.onLabel(1)}>＋ نقطة داخل المنطقة</button>
        <button className={p.label === 0 ? "danger" : ""} onClick={() => p.onLabel(0)}>− نقطة خارجها</button>
      </div>
      <div className="toolbar" style={{ marginBottom: 8 }}>
        <small className="muted">النقاط: {p.points.length}</small>
        {p.busy && <span className="spinner" />}
        <span style={{ flex: 1 }} />
        <button disabled={!p.points.length} onClick={p.onUndo}>تراجع</button>
        <button disabled={!p.points.length} onClick={p.onClear}>مسح</button>
      </div>
      {p.error && <div className="banner danger">{p.error}</div>}
      {p.preview?.message_ar && <div className="banner warn">{p.preview.message_ar}</div>}
      {p.preview?.polygon && (
        <>
          <dl className="kv" style={{ marginBottom: 10 }}>
            <dt>المساحة</dt>
            <dd>{pct(p.preview.area_fraction ?? 0, 2)} من الصورة</dd>
            {p.preview.score !== null && (
              <>
                <dt>درجة النموذج</dt>
                <dd>{p.preview.score.toFixed(2)} <small className="muted">(درجة SAM الداخلية، ليست ثقة في نوع التلف)</small></dd>
              </>
            )}
            {!!p.preview.other_parts && (
              <>
                <dt>ملاحظة</dt>
                <dd>{p.preview.other_parts} جزء صغير آخر لم يُضمّن</dd>
              </>
            )}
          </dl>
          <label>
            نوع التلف للمنطقة الجديدة
            <select value={type} onChange={(e) => setType(e.target.value as DamageType)}>
              {DAMAGE_TYPES.map((t) => <option key={t} value={t}>{DAMAGE[t].label}</option>)}
            </select>
          </label>
          <button className="primary" disabled={p.busy} onClick={() => p.onSaveNew(type)}>حفظ كمنطقة جديدة</button>
          {active.length > 0 && (
            <>
              <label style={{ marginTop: 12 }}>
                أو استبدال حدود منطقة موجودة
                <select value={target} onChange={(e) => setTarget(e.target.value)}>
                  <option value="">— اختر منطقة —</option>
                  {active.map((r) => <option key={r.id} value={r.id}>R{r.index} — {DAMAGE[r.damage_type].label}</option>)}
                </select>
              </label>
              <button disabled={!target || p.busy} onClick={() => p.onApply(target)}>تطبيق الحدود على المنطقة</button>
            </>
          )}
        </>
      )}
    </div>
  );
}
