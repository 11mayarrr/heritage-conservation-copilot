import type { Grid, GridInput } from "../api/types";

export const EMPTY_GRID: GridInput = { cols: 6, rows: 4, width_m: null, height_m: null, note: "" };

export const toGridInput = (g: Grid): GridInput => ({
  cols: g.cols,
  rows: g.rows,
  width_m: g.width_m ?? null,
  height_m: g.height_m ?? null,
  note: g.note ?? "",
});

/** Arabic error message, or null when the grid is valid. Mirrors backend WallGrid. */
export function gridError(g: GridInput): string | null {
  if (!Number.isInteger(g.cols) || g.cols < 1 || g.cols > 26) return "عدد الأعمدة من 1 إلى 26 (A إلى Z).";
  if (!Number.isInteger(g.rows) || g.rows < 1 || g.rows > 30) return "عدد الصفوف من 1 إلى 30.";
  if ((g.width_m == null) !== (g.height_m == null)) return "أدخل العرض والارتفاع معًا، أو اتركهما فارغين.";
  if (g.width_m != null && (g.width_m <= 0 || (g.height_m ?? 0) <= 0)) return "الأبعاد يجب أن تكون أكبر من صفر.";
  return null;
}

export function gridSummary(g: Grid | undefined | null): string {
  if (!g) return "—";
  const kind = g.type === "wall" ? `خاصة بالجدار، الإصدار ${g.version}` : "مؤقتة عامة";
  const size = g.width_m ? ` · الجدار ${g.width_m}×${g.height_m} م` : "";
  return `${g.cols}×${g.rows} (${kind})${size}`;
}

/** True when the case was analysed with a different grid than the wall's current one. */
export function gridOutdated(caseGrid: Grid, wallGrid: Grid | undefined): boolean {
  if (!wallGrid) return false;
  return (caseGrid.version ?? 0) !== (wallGrid.version ?? 0) || caseGrid.cols !== wallGrid.cols || caseGrid.rows !== wallGrid.rows;
}

const colLabel = (i: number) => String.fromCharCode(65 + i);

/** Grid preview with its cell labels, drawn to the wall's aspect ratio when known. */
export function GridPreview({ g }: { g: GridInput }) {
  const cols = Math.max(1, Math.min(26, g.cols || 1));
  const rows = Math.max(1, Math.min(30, g.rows || 1));
  const ratio = g.width_m && g.height_m ? Math.min(4, Math.max(0.5, g.width_m / g.height_m)) : 4 / 3;
  const small = cols * rows > 120;
  return (
    <div
      aria-label="معاينة الشبكة المرجعية"
      style={{
        direction: "ltr", display: "grid", gridTemplateColumns: `repeat(${cols}, 1fr)`, aspectRatio: String(ratio),
        maxHeight: 200, width: "100%", background: "#c9a77c", border: "1px solid #8a6a45", borderRadius: 6, overflow: "hidden",
      }}
    >
      {Array.from({ length: rows * cols }, (_, i) => (
        <div
          key={i}
          style={{
            borderInlineEnd: "1px dashed rgba(255,255,255,.6)", borderBottom: "1px dashed rgba(255,255,255,.6)",
            fontSize: small ? 8 : 11, color: "#3b2a1a", padding: 2, lineHeight: 1,
          }}
        >
          {colLabel(i % cols)}{Math.floor(i / cols) + 1}
        </div>
      ))}
    </div>
  );
}

const num = (v: string): number | null => (v.trim() === "" ? null : Number(v));

export function GridEditor({ value, onChange }: { value: GridInput; onChange: (g: GridInput) => void }) {
  const set = (patch: Partial<GridInput>) => onChange({ ...value, ...patch });
  const err = gridError(value);
  const cell = value.width_m && value.height_m && !err
    ? `${(value.width_m / value.cols).toFixed(2)} × ${(value.height_m / value.rows).toFixed(2)} م`
    : null;
  return (
    <div>
      <div className="row">
        <label>الأعمدة (A، B… من اليسار)
          <input type="number" min={1} max={26} value={value.cols} onChange={(e) => set({ cols: Number(e.target.value) })} />
        </label>
        <label>الصفوف (1، 2… من الأعلى)
          <input type="number" min={1} max={30} value={value.rows} onChange={(e) => set({ rows: Number(e.target.value) })} />
        </label>
      </div>
      <div className="row">
        <label>عرض الجدار بالمتر (اختياري)
          <input type="number" min={0} step="0.01" value={value.width_m ?? ""} onChange={(e) => set({ width_m: num(e.target.value) })} placeholder="مثال: 8.4" />
        </label>
        <label>ارتفاع الجدار بالمتر (اختياري)
          <input type="number" min={0} step="0.01" value={value.height_m ?? ""} onChange={(e) => set({ height_m: num(e.target.value) })} placeholder="مثال: 3.2" />
        </label>
      </div>
      <label>مرجع الشبكة على الجدار
        <input value={value.note} onChange={(e) => set({ note: e.target.value })} placeholder="مثال: العمود A يبدأ من الزاوية الجنوبية الغربية" />
      </label>
      <GridPreview g={value} />
      {cell && <small className="muted">حجم الخلية تقريبًا {cell}. المساحة بالمتر المربع تقديرية، وتصح إذا غطّت الصورة واجهة الجدار كاملة من الأمام.</small>}
      {!value.width_m && <small className="muted">بدون أبعاد تبقى المساحة نسبة من الصورة فقط.</small>}
      {err && <div className="banner danger" style={{ marginTop: 8 }}>{err}</div>}
    </div>
  );
}
