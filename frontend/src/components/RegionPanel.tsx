import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DamageType, Priority, Region, Retrieval } from "../api/types";
import { APPROVE_ONLY_HINT, canApprove } from "../lib/auth";
import { DAMAGE, DAMAGE_TYPES, INSUFFICIENT_AR, PRIORITY } from "../lib/constants";
import { pct } from "../lib/format";
import { Confidence, DamageLabel, RegionFlags } from "./Badges";
import { useAuth } from "./AuthProvider";
import { TreatmentCard } from "./TreatmentCard";

interface Props {
  inspectionId: string;
  region: Region;
  locked: boolean;
  onChanged: (r?: Region) => void;
  onDeleted: () => void;
}

const splitList = (s: string) => s.split(/[،,\n]/).map((x) => x.trim()).filter(Boolean);

export function RegionPanel({ inspectionId, region, locked, onChanged, onDeleted }: Props) {
  const [type, setType] = useState<DamageType>(region.damage_type);
  const [confidence, setConfidence] = useState(region.confidence);
  const [priority, setPriority] = useState<Priority>(region.priority);
  const [note, setNote] = useState(region.note);
  const [field, setField] = useState(region.needs_field_inspection);
  const [treatmentId, setTreatmentId] = useState(region.treatment_id ?? "");
  const [materials, setMaterials] = useState(region.materials.join("، "));
  const [tools, setTools] = useState(region.tools.join("، "));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const { me } = useAuth();
  const mayApprove = canApprove(me?.role);
  const [retrieval, setRetrieval] = useState<Retrieval | null>(null);

  useEffect(() => {
    setType(region.damage_type);
    setConfidence(region.confidence);
    setPriority(region.priority);
    setNote(region.note);
    setField(region.needs_field_inspection);
    setTreatmentId(region.treatment_id ?? "");
    setMaterials(region.materials.join("، "));
    setTools(region.tools.join("، "));
    setReason("");
    setErr(null);
  }, [region]);

  useEffect(() => {
    api.retrieve(type, region.description).then(setRetrieval).catch(() => setRetrieval(null));
  }, [type, region.description]);

  const selectedTreatment = retrieval?.results.find((t) => t.id === treatmentId);

  const run = async (fn: () => Promise<unknown>, after?: () => void) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      after?.();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const save = () =>
    run(async () => {
      const body: Record<string, unknown> = { reason };
      if (type !== region.damage_type) body.damage_type = type;
      if (Math.abs(confidence - region.confidence) > 1e-6) body.confidence = confidence;
      if (priority !== region.priority) body.priority = priority;
      if (note !== region.note) body.note = note;
      if (field !== region.needs_field_inspection) body.needs_field_inspection = field;
      // When the type changes, let the server re-retrieve the treatment unless the expert picked one.
      const typeChanged = type !== region.damage_type;
      if (!typeChanged || treatmentId !== (region.treatment_id ?? "")) {
        if (treatmentId !== (region.treatment_id ?? "")) body.treatment_id = treatmentId || null;
        const m = splitList(materials);
        const t = splitList(tools);
        if (m.join("|") !== region.materials.join("|")) body.materials = m;
        if (t.join("|") !== region.tools.join("|")) body.tools = t;
      }
      const r = await api.updateRegion(inspectionId, region.id, body);
      onChanged(r);
    });

  const pickTreatment = (id: string) => {
    setTreatmentId(id);
    const t = retrieval?.results.find((x) => x.id === id);
    if (t) {
      setMaterials(t.materials.join("، "));
      setTools(t.tools.join("، "));
    }
  };

  return (
    <div className="card">
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>المنطقة R{region.index}</h2>
        <DamageLabel type={region.damage_type} />
      </div>
      <div style={{ margin: "8px 0" }}>
        <RegionFlags r={region} />
      </div>
      <dl className="kv">
        <dt>الثقة</dt>
        <dd><Confidence value={region.confidence} source={region.confidence_source} /></dd>
        <dt>الموقع</dt>
        <dd>{region.grid_cells.join("، ")}</dd>
        <dt>النسبة من الصورة</dt>
        <dd>{pct(region.area_fraction, 2)}</dd>
        <dt>وصف الوكيل</dt>
        <dd>{region.description || "—"}</dd>
      </dl>

      {locked && <div className="banner ok" style={{ marginTop: 10 }}>الحالة معتمدة. أي تعديل سيلغي الاعتماد ويُسجل في السجل.</div>}

      <hr style={{ border: 0, borderTop: "1px solid var(--line)", margin: "12px 0" }} />
      <label>
        نوع التلف
        <select value={type} onChange={(e) => setType(e.target.value as DamageType)}>
          {DAMAGE_TYPES.map((t) => <option key={t} value={t}>{DAMAGE[t].label}</option>)}
        </select>
      </label>
      <div className="row">
        <label>
          درجة الثقة: {Math.round(confidence * 100)}%
          <input type="range" min={0} max={1} step={0.05} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} />
        </label>
        <label>
          الأولوية
          <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
            {(Object.keys(PRIORITY) as Priority[]).map((p) => <option key={p} value={p}>{PRIORITY[p]}</option>)}
          </select>
        </label>
      </div>
      <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input type="checkbox" style={{ width: "auto" }} checked={field} onChange={(e) => setField(e.target.checked)} />
        تحتاج فحصًا ميدانيًا
      </label>
      <label>
        ملاحظة المختص
        <textarea value={note} onChange={(e) => setNote(e.target.value)} />
      </label>

      <label>
        المعالجة المرتبطة (من قاعدة المعرفة فقط)
        <select value={treatmentId} onChange={(e) => pickTreatment(e.target.value)} disabled={!retrieval?.sufficient}>
          <option value="">— بدون معالجة —</option>
          {retrieval?.results.map((t) => <option key={t.id} value={t.id}>{t.title_ar}</option>)}
        </select>
      </label>
      {retrieval && !retrieval.sufficient && <div className="banner warn">{retrieval.message_ar || INSUFFICIENT_AR}</div>}
      <label>
        المواد (افصل بفاصلة)
        <textarea value={materials} onChange={(e) => setMaterials(e.target.value)} style={{ minHeight: 50 }} />
      </label>
      <label>
        الأدوات (افصل بفاصلة)
        <textarea value={tools} onChange={(e) => setTools(e.target.value)} style={{ minHeight: 50 }} />
      </label>
      <label>
        سبب التعديل (يُحفظ في السجل)
        <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="مثال: ظل وليس تشققًا" />
      </label>

      {err && <div className="banner danger">{err}</div>}
      <div className="toolbar">
        <button className="primary" disabled={busy} onClick={save}>حفظ التعديل</button>
        <button className="ok" disabled={busy || !mayApprove || region.status === "approved"} title={mayApprove ? undefined : APPROVE_ONLY_HINT} onClick={() => run(() => api.approveRegion(inspectionId, region.id, reason), () => onChanged())}>اعتماد المنطقة</button>
        <button disabled={busy} onClick={() => run(() => api.returnRegion(inspectionId, region.id, reason), () => onChanged())}>إعادة للمراجعة</button>
        <button className="danger" disabled={busy} onClick={() => run(() => api.deleteRegion(inspectionId, region.id, reason || "نتيجة خاطئة"), onDeleted)}>حذف النتيجة</button>
      </div>

      {selectedTreatment && (
        <div style={{ marginTop: 12 }}>
          <TreatmentCard t={selectedTreatment} compact />
        </div>
      )}
    </div>
  );
}
