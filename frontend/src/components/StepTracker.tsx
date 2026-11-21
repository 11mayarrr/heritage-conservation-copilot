import type { Inspection } from "../api/types";

type State = "done" | "warn" | "current" | "todo" | "fail";

interface Step {
  n: number;
  title: string;
  output: string;
  criterion: string;
  actor: "agent" | "expert";
  state: State;
  note?: string;
}

/**
 * The 10-step action map from the challenge brief (docs/challenge/slide15 and slide16):
 * who does each step, its output and the criterion it is judged by, with this case's status.
 */
export function buildSteps(insp: Inspection): Step[] {
  const active = insp.regions.filter((r) => r.status !== "rejected");
  const ok = insp.quality.acceptable;
  const needTreatment = active.filter((r) => r.damage_type !== "uncertain");
  const missingTreatment = needTreatment.filter((r) => !r.treatment_id);
  const missingMaterials = active.filter((r) => r.treatment_id && r.materials.length + r.tools.length === 0);
  const lowConf = insp.summary.low_confidence;
  const suff = insp.analysis?.sufficiency;
  const approved = insp.status === "approved";
  const touched = insp.summary.edited + insp.summary.approved > 0;
  const s = (cond: boolean, warn = false): State => (!ok ? "todo" : cond ? (warn ? "warn" : "done") : "todo");
  const faces = insp.privacy.faces_hidden ?? 0;
  const manual = insp.privacy.manual_boxes ?? 0;

  return [
    { n: 1, title: "فحص الصورة", output: ok ? "صورة مقبولة" : "طلب إعادة تصوير", criterion: "—", actor: "agent", state: ok ? "done" : "fail",
      note: ok ? (insp.quality.warnings.length ? "الزاوية لا تُقاس آليًا بعد" : undefined) : insp.quality.issues[0] },
    { n: 2, title: "إخفاء الوجوه", output: "صورة خالية من الوجوه", criterion: "الخصوصية", actor: "agent", state: s(true),
      note: ok ? `${faces} آليًا${manual ? ` + ${manual} يدويًا` : ""}` : undefined },
    { n: 3, title: "تحديد التلف", output: "مناطق تلف مصنفة", criterion: "دقة التحديد", actor: "agent", state: s(true),
      note: ok ? `${active.length} منطقة` : undefined },
    { n: 4, title: "تقدير الثقة", output: "درجة ثقة لكل منطقة", criterion: "سهولة المراجعة", actor: "agent",
      state: s(true, lowConf > 0 || (suff ? !suff.sufficient : false)),
      note: ok ? (lowConf > 0 || (suff && !suff.sufficient) ? `غير كافية (${lowConf} منخفضة): يُستشار المختص` : "كافية") : undefined },
    { n: 5, title: "اقتراح المعالجة", output: "رمز المعالجة ووصفها", criterion: "دقة التحديد", actor: "agent",
      state: s(true, missingTreatment.length > 0),
      note: ok ? (missingTreatment.length ? `${missingTreatment.length} بلا معالجة` : "من المكتبة فقط") : undefined },
    { n: 6, title: "المواد والأدوات", output: "قائمة مرتبطة بمواقع التلف", criterion: "دقة التحديد", actor: "agent",
      state: s(true, missingMaterials.length > 0),
      note: ok ? `${insp.materials_by_location?.length ?? 0} بند` : undefined },
    { n: 7, title: "الخريطة الموحدة", output: "خريطة وجدول", criterion: "وضوح الخريطة", actor: "agent", state: s(true),
      note: ok ? `شبكة ${insp.grid.cols}×${insp.grid.rows}${insp.grid.type === "wall" ? "" : " مؤقتة"}` : undefined },
    { n: 8, title: "مراجعة المختص", output: "نسخة مصححة", criterion: "سهولة المراجعة", actor: "expert",
      state: !ok ? "todo" : approved ? "done" : "current",
      note: ok ? (insp.status === "returned" ? "أعيدت من الخطوة 9" : touched ? `${insp.summary.edited} معدّلة · ${insp.summary.approved} معتمدة` : "بانتظار المختص") : undefined },
    { n: 9, title: "الاعتماد", output: "قرار موثّق", criterion: "سهولة المراجعة", actor: "expert",
      state: !ok ? "todo" : approved ? "done" : "todo", note: approved ? `اعتمدها ${insp.approved_by}` : undefined },
    { n: 10, title: "المخرجات المعتمدة", output: approved ? "خريطة · جدول · سجل تصحيحات" : "مخرجات أولية", criterion: "—", actor: "agent",
      state: !ok ? "todo" : approved ? "done" : "warn", note: ok && !approved ? "التقرير الحالي غير معتمد" : undefined },
  ];
}

const TONE: Record<State, { bg: string; fg: string; icon: string; label: string }> = {
  done: { bg: "#e3ede3", fg: "#2e4c33", icon: "✓", label: "تمت" },
  warn: { bg: "#fbecd2", fg: "#6b4300", icon: "!", label: "تمت مع ملاحظة" },
  current: { bg: "#dbe6f4", fg: "#1f3a5f", icon: "●", label: "الخطوة الحالية" },
  todo: { bg: "#efe7da", fg: "#8a7a66", icon: "○", label: "لم تبدأ" },
  fail: { bg: "#f8e1df", fg: "#7d1a14", icon: "✕", label: "متوقفة" },
};

/** Action-map strip shown at the top of each case. */
export function StepTracker({ insp }: { insp: Inspection }) {
  const steps = buildSteps(insp);
  return (
    <details className="card" open style={{ padding: 12 }}>
      <summary style={{ cursor: "pointer" }}>
        <b>خريطة إجراءات الوكيل</b>{" "}
        <small className="muted">· الحد الداكن: ينفذها الوكيل · الحد الأزرق: ينفذها المختص. الوكيل يقترح، والمختص يقرر.</small>
      </summary>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 6, marginTop: 8 }}>
        {steps.map((st) => {
          const t = TONE[st.state];
          return (
            <div
              key={st.n}
              title={`${t.label}\nالمخرج: ${st.output}\nالمعيار: ${st.criterion}`}
              style={{
                background: t.bg, color: t.fg, borderRadius: 8, padding: "6px 8px", fontSize: "0.78rem",
                borderInlineStart: `4px solid ${st.actor === "expert" ? "#2f7de1" : "#1b2238"}`,
              }}
            >
              <div style={{ display: "flex", gap: 4, justifyContent: "space-between" }}>
                <b>{st.n}. {st.title}</b>
                <b aria-label={t.label}>{t.icon}</b>
              </div>
              <div>{st.output}</div>
              {st.criterion !== "—" && <div style={{ opacity: 0.75 }}>المعيار: {st.criterion}</div>}
              {st.note && <div style={{ opacity: 0.9, marginTop: 2 }}>{st.note}</div>}
            </div>
          );
        })}
      </div>
    </details>
  );
}
