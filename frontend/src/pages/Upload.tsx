import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, urls } from "../api/client";
import type { Inspection } from "../api/types";
import { DamageLabel, InspectionStatusBadge } from "../components/Badges";
import { DetectorNotice, PrivacyNotice } from "../components/Notices";
import { pct } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Upload() {
  const walls = useAsync(() => api.walls(), []);
  const [wallId, setWallId] = useState("");
  const [newCode, setNewCode] = useState("");
  const [newBuilding, setNewBuilding] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [captured, setCaptured] = useState(() => new Date().toISOString().slice(0, 10));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<Inspection | null>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const choose = (f: File | undefined) => {
    if (!f) return;
    setFile(f);
    setResult(null);
    // Local preview only; nothing is uploaded until "تحليل".
    setPreview(URL.createObjectURL(f));
  };

  const createWall = async () => {
    setErr(null);
    try {
      const w = await api.createWall(newCode.trim(), newBuilding.trim());
      await walls.reload();
      setWallId(w.id);
      setNewCode("");
      setNewBuilding("");
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const analyze = async () => {
    if (!file || !wallId) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.upload(wallId, file, captured ? `${captured}T12:00:00` : undefined);
      setResult(r);
      if (preview) URL.revokeObjectURL(preview);
      setPreview(null);
      void walls.reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1>رفع وتحليل الصور</h1>
      <PrivacyNotice />
      <div className="grid cols-2">
        <div className="card">
          <h2>1. الجدار</h2>
          <label>
            اختر الجدار
            <select value={wallId} onChange={(e) => setWallId(e.target.value)}>
              <option value="">— اختر —</option>
              {walls.data?.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} {w.building_name ? `— ${w.building_name}` : ""} ({w.inspection_count} صورة)
                </option>
              ))}
            </select>
          </label>
          <details>
            <summary>تسجيل جدار جديد</summary>
            <div className="row" style={{ marginTop: 8 }}>
              <label>رقم الجدار<input value={newCode} onChange={(e) => setNewCode(e.target.value)} placeholder="مثال: TRF-A12-N" /></label>
              <label>اسم المبنى<input value={newBuilding} onChange={(e) => setNewBuilding(e.target.value)} /></label>
            </div>
            <button onClick={createWall} disabled={!newCode.trim()}>تسجيل الجدار</button>
          </details>
          <h2 style={{ marginTop: 14 }}>2. الصورة</h2>
          <div
            className={`dropzone${drag ? " drag" : ""}`}
            onClick={() => input.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); choose(e.dataTransfer.files[0]); }}
          >
            {file ? <b>{file.name}</b> : "اسحب صورة الجدار هنا أو انقر للاختيار (JPG أو PNG)"}
            <input ref={input} type="file" accept="image/jpeg,image/png" hidden onChange={(e) => choose(e.target.files?.[0])} />
          </div>
          <label style={{ marginTop: 10 }}>
            تاريخ التصوير
            <input type="date" value={captured} onChange={(e) => setCaptured(e.target.value)} />
          </label>
          <small className="muted">صوّر الجدار بشكل عمودي، في إضاءة متجانسة، ومن نفس الموقع في كل زيارة لتسهيل المقارنة الزمنية.</small>
          {err && <div className="banner danger" style={{ marginTop: 10 }}>{err}</div>}
          <div className="toolbar" style={{ marginTop: 10 }}>
            <button className="primary" disabled={!file || !wallId || busy} onClick={analyze}>
              {busy ? <span className="spinner" /> : null} تحليل الصورة
            </button>
            {!wallId && <small className="muted">اختر الجدار أولًا.</small>}
          </div>
        </div>

        <div className="card">
          {!result && preview && (
            <>
              <h2>معاينة محلية</h2>
              <small className="muted">لم تُرفع الصورة بعد. ستُخفى الوجوه قبل الحفظ.</small>
              <img src={preview} className="preview" alt="معاينة" />
            </>
          )}
          {!result && !preview && <div className="empty">ستظهر نتيجة التحليل هنا.</div>}
          {result && <UploadResult r={result} />}
        </div>
      </div>
    </>
  );
}

function UploadResult({ r }: { r: Inspection }) {
  if (r.status === "rejected_quality") {
    return (
      <>
        <div className="toolbar" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>الحالة {r.case_number}</h2>
          <InspectionStatusBadge status={r.status} />
        </div>
        <div className="banner danger" style={{ marginTop: 10 }}>
          <b>الصورة غير صالحة للتحليل، يرجى إعادة التصوير:</b>
          <ul>{r.quality.issues.map((i) => <li key={i}>{i}</li>)}</ul>
        </div>
        <small className="muted">لم تُحفظ الصورة. الوضوح {r.quality.sharpness}، السطوع {r.quality.brightness}.</small>
      </>
    );
  }
  return (
    <>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>الحالة {r.case_number}</h2>
        <InspectionStatusBadge status={r.status} />
      </div>
      <DetectorNotice detector={r.analysis?.detector} />
      <img src={urls.image(r.id)} className="preview" alt="الصورة بعد إخفاء الوجوه" />
      <p>
        تم إخفاء <b>{r.privacy.faces_hidden ?? 0}</b> وجه آليًا. عدد المناطق المقترحة: <b>{r.summary.total}</b>، منها{" "}
        <b>{r.summary.low_confidence}</b> منخفضة الثقة و<b>{r.summary.field_inspection}</b> تحتاج فحصًا ميدانيًا.
      </p>
      {Object.entries(r.summary.by_type).map(([t, v]) => (
        <div key={t}>
          <DamageLabel type={t as never} /> — {v.count} منطقة، {pct(v.area_fraction, 2)} من الصورة
        </div>
      ))}
      {r.analysis?.sufficiency && (
        <div className={`banner ${r.analysis.sufficiency.sufficient ? "ok" : "warn"}`} style={{ marginTop: 10 }}>
          {r.analysis.sufficiency.recommendation_ar}
          <ul>{r.analysis.sufficiency.reasons_ar.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      )}
      {r.quality.warnings.length > 0 && <small className="muted">ملاحظات الجودة: {r.quality.warnings.join(" ")}</small>}
      <div className="toolbar" style={{ marginTop: 10 }}>
        <Link className="btn primary" to={`/atlas/${r.id}`}>فتح خريطة التلف للمراجعة</Link>
        <a className="btn" href={urls.image(r.id, true)}>تنزيل الصورة بعد إخفاء الوجوه</a>
      </div>
    </>
  );
}
