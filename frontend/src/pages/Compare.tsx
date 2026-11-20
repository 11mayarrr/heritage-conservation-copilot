import { useMemo, useState } from "react";
import { api, urls } from "../api/client";
import type { Comparison, Inspection } from "../api/types";
import { AtlasEditor, type Overlay } from "../components/AtlasEditor";
import { DamageLabel } from "../components/Badges";
import { DAMAGE } from "../lib/constants";
import { formatDate, pct } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const STATUS_COLOR: Record<string, string> = { new: "#D32F2F", grew: "#F57C00", unchanged: "#5F7F68", not_found: "#8A8A8A" };
const STATUS_AR: Record<string, string> = { new: "جديدة", grew: "زاد فيها التلف", unchanged: "لم تتغير", not_found: "غير ظاهرة في الأحدث" };

export default function Compare() {
  const walls = useAsync(() => api.walls(), []);
  const [wallId, setWallId] = useState("");
  const [beforeId, setBeforeId] = useState("");
  const [afterId, setAfterId] = useState("");
  const [result, setResult] = useState<Comparison | null>(null);
  const [before, setBefore] = useState<Inspection | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showCandidates, setShowCandidates] = useState(false);

  const wall = walls.data?.find((w) => w.id === wallId);
  const options = (wall?.inspections ?? []).filter((i) => i.has_image);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      const c = await api.compare(beforeId, afterId);
      setResult(c);
      setBefore(await api.inspection(c.before.id));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const overlays: Overlay[] = useMemo(() => {
    if (!result) return [];
    const items = result.regions.items.map((it, k) => ({
      key: `i${k}`,
      polygon: it.polygon_in_before,
      color: STATUS_COLOR[it.status],
      label: STATUS_AR[it.status],
      dashed: it.status === "not_found",
      fill: it.status === "unchanged" ? 0.1 : 0.25,
    }));
    const cands = showCandidates
      ? result.visual_candidates.candidates.map((c, k) => ({ key: `c${k}`, polygon: c.polygon, color: "#cccccc", dashed: true, fill: 0.08 }))
      : [];
    return [...items, ...cands];
  }, [result, showCandidates]);

  return (
    <>
      <h1>المقارنة الزمنية</h1>
      <div className="card">
        <div className="row">
          <label>
            الجدار
            <select value={wallId} onChange={(e) => { setWallId(e.target.value); setBeforeId(""); setAfterId(""); setResult(null); }}>
              <option value="">— اختر —</option>
              {walls.data?.filter((w) => w.inspections.filter((i) => i.has_image).length > 1).map((w) => <option key={w.id} value={w.id}>{w.code} ({w.inspections.filter((i) => i.has_image).length} صور مقبولة)</option>)}
            </select>
          </label>
          <label>
            الصورة الأقدم
            <select value={beforeId} onChange={(e) => setBeforeId(e.target.value)} disabled={!wall}>
              <option value="">—</option>
              {options.map((i) => <option key={i.id} value={i.id}>{i.case_number} — {formatDate(i.captured_at)}</option>)}
            </select>
          </label>
          <label>
            الصورة الأحدث
            <select value={afterId} onChange={(e) => setAfterId(e.target.value)} disabled={!wall}>
              <option value="">—</option>
              {options.filter((i) => i.id !== beforeId).map((i) => <option key={i.id} value={i.id}>{i.case_number} — {formatDate(i.captured_at)}</option>)}
            </select>
          </label>
        </div>
        <button className="primary" disabled={!beforeId || !afterId || busy} onClick={run}>
          {busy && <span className="spinner" />} مقارنة
        </button>
        {walls.data && walls.data.every((w) => w.inspections.filter((i) => i.has_image).length < 2) && (
          <p className="muted">تحتاج المقارنة صورتين على الأقل لنفس الجدار.</p>
        )}
        {err && <div className="banner danger" style={{ marginTop: 10 }}>{err}</div>}
      </div>

      {result && (
        <>
          <div className={`banner ${result.registration.ok ? "ok" : "danger"}`} style={{ marginTop: 14 }}>
            <b>محاذاة الصورتين:</b> {result.registration.message_ar}{" "}
            <small>(تطابقات {result.registration.matches}، موثوقة {result.registration.inliers})</small>
          </div>
          <div className="grid cols-4">
            {(["new", "grew", "unchanged", "not_found"] as const).map((s) => (
              <div className="stat" key={s} style={{ borderInlineStart: `5px solid ${STATUS_COLOR[s]}` }}>
                <div className="v">{result.regions.summary[s] ?? 0}</div>
                <div className="l">{STATUS_AR[s]}</div>
              </div>
            ))}
          </div>
          <div className="grid cols-2" style={{ marginTop: 14 }}>
            <div className="card">
              <h2>التغيرات على الصورة الأقدم</h2>
              {before && (
                <AtlasEditor
                  imageUrl={urls.image(before.id)}
                  naturalWidth={before.width}
                  naturalHeight={before.height}
                  regions={[]}
                  overlays={overlays}
                  maxHeight={480}
                />
              )}
              <label style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 8 }}>
                <input type="checkbox" checked={showCandidates} onChange={(e) => setShowCandidates(e.target.checked)} style={{ width: "auto" }} />
                عرض مناطق التغير البصري المرشحة (ثقة منخفضة)
              </label>
              <small className="muted">{result.visual_candidates.reason_ar}</small>
            </div>
            <div className="card">
              <h2>قبل / بعد</h2>
              <img className="compare-img" src={urls.comparisonImage(result.id, "side_by_side")} alt="قبل وبعد" />
              <small className="muted">
                {result.before.case_number} ({formatDate(result.before.captured_at)}) ← {result.after.case_number} ({formatDate(result.after.captured_at)})
                {result.registration.ok ? "، الصورة الأحدث بعد المحاذاة." : "، بدون محاذاة."}
              </small>
            </div>
          </div>
          <div className="card">
            <h2>تفاصيل التغير</h2>
            <div className="table-wrap">
              <table>
                <thead><tr><th>النوع</th><th>في الأقدم</th><th>في الأحدث</th><th>التغير</th><th>تغير المساحة</th><th>التداخل (IoU)</th></tr></thead>
                <tbody>
                  {result.regions.items.map((it, k) => (
                    <tr key={k}>
                      <td><DamageLabel type={it.damage_type} /></td>
                      <td>{it.before_index ? `R${it.before_index}` : "—"}</td>
                      <td>{it.after_index ? `R${it.after_index}` : "—"}</td>
                      <td><span className="badge" style={{ background: STATUS_COLOR[it.status], color: "#fff" }}>{it.status_ar}</span></td>
                      <td>{it.area_change === null ? "—" : `${it.area_change > 0 ? "+" : ""}${pct(it.area_change)}`}</td>
                      <td>{it.iou.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="muted">{result.notes_ar.map((n) => <li key={n}>{n}</li>)}</ul>
            <small className="muted">ألوان المقارنة خاصة بهذه الصفحة: الأحمر جديد، البرتقالي زاد، الأخضر لم يتغير، الرمادي غير ظاهر. ألوان أنواع التلف: {Object.values(DAMAGE).map((d) => d.label).join("، ")}.</small>
          </div>
        </>
      )}
    </>
  );
}
