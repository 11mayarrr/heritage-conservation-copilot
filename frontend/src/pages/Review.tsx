import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { RegionStatus } from "../api/types";
import { Confidence, DamageLabel, InspectionStatusBadge, RegionFlags } from "../components/Badges";
import { InspectionPicker } from "../components/InspectionPicker";
import { GridOutdatedNotice } from "../components/GridOutdatedNotice";
import { DetectorNotice } from "../components/Notices";
import { StepTracker } from "../components/StepTracker";
import { PRIORITY, REGION_STATUS } from "../lib/constants";
import { formatDate, pct } from "../lib/format";
import { useAsync } from "../lib/useAsync";

type Filter = "all" | RegionStatus | "low" | "field";

export default function Review() {
  const { id } = useParams();
  if (!id) return <InspectionPicker basePath="/review" title="المراجعة والتصحيح" />;
  return <ReviewWorkspace id={id} />;
}

function ReviewWorkspace({ id }: { id: string }) {
  const { data: insp, error, reload } = useAsync(() => api.inspection(id), [id]);
  const [filter, setFilter] = useState<Filter>("all");
  const [notes, setNotes] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const rows = useMemo(() => {
    const rs = insp?.regions ?? [];
    if (filter === "all") return rs;
    if (filter === "low") return rs.filter((r) => r.low_confidence);
    if (filter === "field") return rs.filter((r) => r.needs_field_inspection);
    return rs.filter((r) => r.status === filter);
  }, [insp, filter]);

  if (error) return <div className="banner danger">{error}</div>;
  if (!insp) return <span className="spinner" />;
  const hasM2 = insp.regions.some((r) => r.area_m2 != null);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const s = insp.summary;
  const filters: [Filter, string, number][] = [
    ["all", "الكل", s.total],
    ["agent", REGION_STATUS.agent.label, s.agent],
    ["edited", REGION_STATUS.edited.label, s.edited],
    ["approved", REGION_STATUS.approved.label, s.approved],
    ["needs_review", REGION_STATUS.needs_review.label, s.needs_review],
    ["low", "منخفضة الثقة", s.low_confidence],
    ["field", "تحتاج فحصًا ميدانيًا", s.field_inspection],
  ];

  return (
    <>
      <div className="topbar">
        <div>
          <h1>المراجعة والتصحيح — {insp.case_number}</h1>
          <small className="muted">جدار {insp.wall.code} · {formatDate(insp.captured_at)}</small>
        </div>
        <InspectionStatusBadge status={insp.status} />
      </div>
      <StepTracker insp={insp} />
      <DetectorNotice detector={insp.analysis?.detector} />
      <GridOutdatedNotice insp={insp} onApplied={() => void reload()} />
      {insp.status === "approved" && (
        <div className="banner ok">اعتمدها {insp.approved_by} في {formatDate(insp.approved_at, true)}. أي تعديل لاحق يلغي الاعتماد تلقائيًا.</div>
      )}
      {err && <div className="banner danger">{err}</div>}

      <div className="card">
        <div className="tabs">
          {filters.map(([f, label, n]) => (
            <button key={f} className={filter === f ? "active" : ""} onClick={() => setFilter(f)}>
              {label} ({n})
            </button>
          ))}
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>المنطقة</th><th>النوع</th><th>الموقع</th><th>النسبة</th>{hasM2 && <th>م² تقديري</th>}<th>الثقة</th><th>الأولوية</th><th>الحالة</th><th>ملاحظة</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td><b>R{r.index}</b></td>
                  <td><DamageLabel type={r.damage_type} /></td>
                  <td>{r.grid_cells.join("، ")}</td>
                  <td>{pct(r.area_fraction, 2)}</td>
                  {hasM2 && <td>{r.area_m2 != null ? `≈ ${r.area_m2.toFixed(2)}` : "—"}</td>}
                  <td><Confidence value={r.confidence} source={r.confidence_source} /></td>
                  <td>{PRIORITY[r.priority]}</td>
                  <td><RegionFlags r={r} /></td>
                  <td>{r.note || "—"}</td>
                  <td>
                    <div className="toolbar">
                      <Link className="btn" to={`/atlas/${id}`}>تعديل</Link>
                      {r.status !== "approved" && (
                        <button className="ok" disabled={busy} onClick={() => run(() => api.approveRegion(id, r.id))}>اعتماد</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={hasM2 ? 10 : 9} className="empty">لا توجد مناطق في هذا التصنيف.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 14 }}>
        <div className="card">
          <h2>ملاحظات المختص العامة</h2>
          <textarea value={notes ?? insp.expert_notes} onChange={(e) => setNotes(e.target.value)} />
          <button disabled={busy || notes === null} onClick={() => run(async () => { await api.setNotes(id, notes ?? ""); setNotes(null); })}>حفظ الملاحظات</button>
        </div>
        <div className="card">
          <h2>قرار الاعتماد</h2>
          <p className="muted">اعتماد الحالة يعتمد كل المناطق غير المحذوفة. لا يمكن الاعتماد إذا وُجدت مناطق معادة للمراجعة.</p>
          <label>سبب القرار (يُحفظ في السجل)<input value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <div className="toolbar">
            <button className="ok" disabled={busy || insp.status === "approved"} onClick={() => run(() => api.approve(id, reason))}>اعتماد النتيجة</button>
            <button disabled={busy} onClick={() => run(() => api.returnForReview(id, reason))}>إعادة للمراجعة</button>
            <button disabled={busy} onClick={() => run(() => api.reanalyze(id))} title="إعادة حساب المساحات والمواقع وربط المعالجات الناقصة">إعادة التحليل بعد التعديل</button>
            <Link className="btn navy" to={`/reports?id=${id}`}>التقرير</Link>
          </div>
        </div>
      </div>
    </>
  );
}
