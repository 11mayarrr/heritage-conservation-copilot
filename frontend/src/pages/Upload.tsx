import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, urls } from "../api/client";
import type { GridInput, Inspection } from "../api/types";
import { DamageLabel, InspectionStatusBadge } from "../components/Badges";
import { EMPTY_GRID, GridEditor, GridPreview, gridError, gridSummary, toGridInput } from "../components/GridEditor";
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
  const [withGrid, setWithGrid] = useState(true);
  const [newGrid, setNewGrid] = useState<GridInput>(EMPTY_GRID);
  const [editGrid, setEditGrid] = useState<GridInput | null>(null);
  const [applyOpen, setApplyOpen] = useState(true);
  const [gridMsg, setGridMsg] = useState<string | null>(null);
  const wall = walls.data?.find((w) => w.id === wallId);
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
      const w = await api.createWall(newCode.trim(), newBuilding.trim(), "", withGrid ? newGrid : null);
      await walls.reload();
      setWallId(w.id);
      setNewCode("");
      setNewBuilding("");
      setNewGrid(EMPTY_GRID);
      setEditGrid(null);
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const saveGrid = async () => {
    if (!wall || !editGrid) return;
    setErr(null);
    setGridMsg(null);
    try {
      const out = await api.setWallGrid(wall.id, editGrid, applyOpen, "تعديل الشبكة المرجعية للجدار");
      await walls.reload();
      setEditGrid(null);
      const parts = [`حُفظت الشبكة (الإصدار ${out.grid.version}). الصور الجديدة تُحلل بها.`];
      if (out.applied_to.length) parts.push(`طُبقت على: ${out.applied_to.join("، ")}.`);
      if (out.kept_previous_grid.length) parts.push(`بقيت بشبكتها الأصلية لأنها معتمدة: ${out.kept_previous_grid.join("، ")}.`);
      setGridMsg(parts.join(" "));
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
            <select value={wallId} onChange={(e) => { setWallId(e.target.value); setEditGrid(null); setGridMsg(null); }}>
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
            <label style={{ display: "flex", gap: 6, alignItems: "center", margin: "8px 0" }}>
              <input type="checkbox" checked={withGrid} onChange={(e) => setWithGrid(e.target.checked)} style={{ width: "auto" }} />
              <b>شبكة مرجعية خاصة بهذا الجدار</b>
            </label>
            {withGrid ? (
              <GridEditor value={newGrid} onChange={setNewGrid} />
            ) : (
              <small className="muted">بدونها تُستخدم الشبكة المؤقتة العامة، ويمكن تحديدها لاحقًا.</small>
            )}
            <div style={{ marginTop: 8 }}>
              <button onClick={createWall} disabled={!newCode.trim() || (withGrid && !!gridError(newGrid))}>تسجيل الجدار</button>
            </div>
          </details>
          {wall && (
            <div className="banner info" style={{ marginTop: 10 }}>
              <div className="toolbar" style={{ justifyContent: "space-between" }}>
                <b>الشبكة المرجعية للجدار {wall.code}</b>
                <span className={`badge ${wall.grid.type === "wall" ? "approved" : "review"}`}>{wall.grid.type === "wall" ? "خاصة بالجدار" : "مؤقتة"}</span>
              </div>
              <div>{gridSummary(wall.grid)}{wall.grid.note ? ` · ${wall.grid.note}` : ""}</div>
              {editGrid ? (
                <div style={{ marginTop: 8 }}>
                  <GridEditor value={editGrid} onChange={setEditGrid} />
                  <label style={{ display: "flex", gap: 6, alignItems: "center", margin: "8px 0" }}>
                    <input type="checkbox" checked={applyOpen} onChange={(e) => setApplyOpen(e.target.checked)} style={{ width: "auto" }} />
                    طبّقها أيضًا على صور هذا الجدار غير المعتمدة (المعتمدة تبقى بشبكتها)
                  </label>
                  <div className="toolbar">
                    <button className="primary" disabled={!!gridError(editGrid)} onClick={saveGrid}>حفظ الشبكة</button>
                    <button onClick={() => setEditGrid(null)}>إلغاء</button>
                  </div>
                </div>
              ) : (
                <div style={{ marginTop: 8 }}>
                  <GridPreview g={toGridInput(wall.grid)} />
                  <button style={{ marginTop: 8 }} onClick={() => setEditGrid(toGridInput(wall.grid))}>
                    {wall.grid.type === "wall" ? "تعديل الشبكة" : "تحديد شبكة لهذا الجدار"}
                  </button>
                </div>
              )}
              {gridMsg && <div className="banner ok" style={{ marginTop: 8, marginBottom: 0 }}>{gridMsg}</div>}
            </div>
          )}
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
