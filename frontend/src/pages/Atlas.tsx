import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, urls } from "../api/client";
import type { DamageType, Point, SegmentPreview } from "../api/types";
import { AtlasEditor } from "../components/AtlasEditor";
import { Confidence, DamageLabel, InspectionStatusBadge, Legend, RegionFlags } from "../components/Badges";
import { InspectionPicker } from "../components/InspectionPicker";
import { GridOutdatedNotice } from "../components/GridOutdatedNotice";
import { gridSummary } from "../components/GridEditor";
import { DetectorNotice } from "../components/Notices";
import { RegionPanel } from "../components/RegionPanel";
import { SmartSelectPanel } from "../components/SmartSelectPanel";
import { StepTracker } from "../components/StepTracker";
import { DAMAGE, DAMAGE_TYPES } from "../lib/constants";
import { formatDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";

type Mode = "select" | "draw" | "blur" | "smart";

export default function Atlas() {
  const { id } = useParams();
  if (!id) return <InspectionPicker basePath="/atlas" title="خريطة التلف" />;
  return <AtlasWorkspace id={id} />;
}

function AtlasWorkspace({ id }: { id: string }) {
  const { data: insp, error, reload } = useAsync(() => api.inspection(id), [id]);
  const [selected, setSelected] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("select");
  const [drawType, setDrawType] = useState<DamageType>("crack");
  const [showGrid, setShowGrid] = useState(true);
  const [imgVersion, setImgVersion] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [points, setPoints] = useState<[number, number, number][]>([]);
  const [pointLabel, setPointLabel] = useState<0 | 1>(1);
  const [preview, setPreview] = useState<SegmentPreview | null>(null);
  const [segBusy, setSegBusy] = useState(false);
  const [segErr, setSegErr] = useState<string | null>(null);
  const [smartTarget, setSmartTarget] = useState<string | null>(null);

  if (error) return <div className="banner danger">{error}</div>;
  if (!insp) return <span className="spinner" />;
  if (!insp.has_image)
    return <div className="banner danger">هذه الحالة مرفوضة لجودة الصورة ولا تحتوي على صورة. <Link to="/upload">ارفع صورة جديدة</Link></div>;

  const region = insp.regions.find((r) => r.id === selected) ?? null;
  const locked = insp.status === "approved";

  const savePolygon = async (rid: string, polygon: Point[]) => {
    setErr(null);
    try {
      await api.updateRegion(id, rid, { polygon, reason: "تعديل الحدود على الخريطة" });
      await reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const finishDraw = async (polygon: Point[]) => {
    setErr(null);
    try {
      if (mode === "blur") {
        const xs = polygon.map((p) => p[0]);
        const ys = polygon.map((p) => p[1]);
        const box = [Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)];
        await api.manualBlur(id, [box], "إخفاء يدوي لوجه أو شخص");
        setImgVersion((v) => v + 1);
      } else {
        const r = await api.addRegion(id, { damage_type: drawType, polygon, confidence: 1, reason: "إضافة يدوية" });
        setSelected(r.id);
      }
      setMode("select");
      await reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const runSegment = async (pts: [number, number, number][]) => {
    setPoints(pts);
    setSegErr(null);
    if (!pts.some((q) => q[2] === 1)) {
      setPreview(null);
      return;
    }
    setSegBusy(true);
    try {
      setPreview(await api.segment(id, pts));
    } catch (e) {
      setSegErr((e as Error).message);
    } finally {
      setSegBusy(false);
    }
  };

  const resetSmart = () => {
    setPoints([]);
    setPreview(null);
    setSegErr(null);
  };

  const smartTool = preview?.segmenter.kind === "sam2" ? "SAM 2" : "GrabCut";

  const saveSmartNew = async (type: DamageType) => {
    if (!preview?.polygon) return;
    try {
      const r = await api.addRegion(id, {
        damage_type: type,
        polygon: preview.polygon,
        confidence: 1,
        reason: `إضافة بالتحديد الذكي (${smartTool})`,
      });
      resetSmart();
      setMode("select");
      setSelected(r.id);
      await reload();
    } catch (e) {
      setSegErr((e as Error).message);
    }
  };

  const applySmart = async (rid: string) => {
    if (!preview?.polygon) return;
    try {
      await api.updateRegion(id, rid, { polygon: preview.polygon, reason: `تحسين الحدود بالتحديد الذكي (${smartTool})` });
      resetSmart();
      setMode("select");
      setSelected(rid);
      await reload();
    } catch (e) {
      setSegErr((e as Error).message);
    }
  };

  return (
    <>
      <div className="topbar">
        <div>
          <h1>خريطة التلف — {insp.case_number}</h1>
          <small className="muted">
            جدار {insp.wall.code} {insp.wall.building_name && `· ${insp.wall.building_name}`} · تاريخ التصوير {formatDate(insp.captured_at)} · الشبكة المرجعية{" "}
            {gridSummary(insp.grid)}
          </small>
        </div>
        <InspectionStatusBadge status={insp.status} />
      </div>
      <StepTracker insp={insp} />
      <DetectorNotice detector={insp.analysis?.detector} />
      <GridOutdatedNotice insp={insp} onApplied={() => void reload()} />
      {err && <div className="banner danger">{err}</div>}

      <div className="workspace">
        <div className="card">
          <div className="toolbar" style={{ marginBottom: 8 }}>
            <button className={mode === "select" ? "navy" : ""} onClick={() => setMode("select")}>تحديد وتعديل</button>
            <button className={mode === "draw" ? "navy" : ""} onClick={() => { setMode("draw"); setSelected(null); }}>إضافة منطقة يدويًا</button>
            {mode === "draw" && (
              <select value={drawType} onChange={(e) => setDrawType(e.target.value as DamageType)} style={{ width: "auto" }}>
                {DAMAGE_TYPES.map((t) => <option key={t} value={t}>{DAMAGE[t].label}</option>)}
              </select>
            )}
            <button
              className={mode === "smart" ? "navy" : ""}
              onClick={() => { setSmartTarget(selected); setMode("smart"); setSelected(null); resetSmart(); }}
              title="انقر على منطقة فيرسم النظام حدودها (SAM 2 أو GrabCut)"
            >
              تحديد ذكي
            </button>
            <button className={mode === "blur" ? "navy" : ""} onClick={() => { setMode("blur"); setSelected(null); }}>إخفاء يدوي</button>
            <label style={{ display: "inline-flex", gap: 6, alignItems: "center", margin: 0 }}>
              <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} style={{ width: "auto" }} /> الشبكة
            </label>
            <span style={{ flex: 1 }} />
            <a className="btn" href={urls.atlas(id, true)}>تنزيل الخريطة</a>
            <a className="btn" href={urls.image(id, true)}>تنزيل الصورة المخفية</a>
          </div>
          <AtlasEditor
            imageUrl={`${urls.image(id)}?v=${imgVersion}`}
            naturalWidth={insp.width}
            naturalHeight={insp.height}
            regions={insp.regions}
            selectedId={selected}
            onSelect={setSelected}
            editable={mode === "select"}
            onPolygonChange={savePolygon}
            drawMode={mode === "draw" || mode === "blur"}
            pointMode={mode === "smart"}
            pointLabel={pointLabel}
            onPoint={(pt, lab) => void runSegment([...points, [pt[0], pt[1], lab]])}
            promptPoints={mode === "smart" ? points : []}
            overlays={
              mode === "smart" && preview?.polygon
                ? [{ key: "preview", polygon: preview.polygon, color: "#ffffff", dashed: true, fill: 0.25 }]
                : []
            }
            drawType={mode === "blur" ? "uncertain" : drawType}
            onDrawComplete={finishDraw}
            onDrawCancel={() => setMode("select")}
            grid={showGrid ? insp.grid : null}
          />
          <Legend />
          <small className="muted">
            الخط المتقطع: تآكل حواف، أو تلف غير مؤكد، أو ثقة منخفضة. الأعمدة A، B… من اليسار والصفوف 1، 2… من الأعلى.{" "}
            {insp.grid.width_m
              ? "المساحة بالمتر المربع تقديرية من أبعاد الجدار المسجلة، وتصح إذا غطّت الصورة واجهة الجدار كاملة من الأمام."
              : "تُعرض المساحات نسبةً من الصورة، لأن الجدار بلا أبعاد مسجلة (أضفها في شبكة الجدار من صفحة الرفع)."}
          </small>
        </div>

        <div>
          {mode === "smart" ? (
            <SmartSelectPanel
              points={points}
              label={pointLabel}
              onLabel={setPointLabel}
              preview={preview}
              busy={segBusy}
              error={segErr}
              regions={insp.regions}
              initialTarget={smartTarget}
              onUndo={() => void runSegment(points.slice(0, -1))}
              onClear={resetSmart}
              onSaveNew={saveSmartNew}
              onApply={applySmart}
            />
          ) : region ? (
            <RegionPanel
              inspectionId={id}
              region={region}
              locked={locked}
              onChanged={() => void reload()}
              onDeleted={() => { setSelected(null); void reload(); }}
            />
          ) : (
            <div className="card">
              <h2>المناطق ({insp.regions.length})</h2>
              <p className="muted">انقر على منطقة في الخريطة أو في القائمة لمراجعتها.</p>
              {insp.regions.length === 0 && <div className="empty">لم يكتشف الوكيل مناطق. أضف مناطق يدويًا عند الحاجة.</div>}
              {insp.regions.map((r) => (
                <div key={r.id} className="card" style={{ padding: 10, cursor: "pointer" }} onClick={() => setSelected(r.id)}>
                  <div className="toolbar" style={{ justifyContent: "space-between" }}>
                    <b>R{r.index}</b>
                    <DamageLabel type={r.damage_type} />
                  </div>
                  <Confidence value={r.confidence} source={r.confidence_source} />
                  <div style={{ marginTop: 4 }}><RegionFlags r={r} /></div>
                </div>
              ))}
              <div className="toolbar" style={{ marginTop: 10 }}>
                <Link className="btn navy" to={`/review/${id}`}>الانتقال إلى المراجعة والاعتماد</Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
