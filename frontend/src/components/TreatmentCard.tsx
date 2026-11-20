import type { Treatment } from "../api/types";

export function SourceList({ t, max = 3 }: { t: Treatment; max?: number }) {
  return (
    <div>
      {t.sources.slice(0, max).map((s, i) => (
        <div key={i} style={{ marginBottom: 6 }}>
          <small>
            <b>المصدر:</b>{" "}
            {s.url ? (
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title}
              </a>
            ) : (
              s.title
            )}{" "}
            — {s.publisher}، {s.year} — <span dir="ltr">{s.locator}</span>
          </small>
          {s.quote && <div className="src-quote">“{s.quote}”</div>}
        </div>
      ))}
    </div>
  );
}

export function TreatmentCard({ t, compact = false }: { t: Treatment; compact?: boolean }) {
  return (
    <div className="card" style={{ padding: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>{t.title_ar}</h3>
        <span className={`badge ${t.approval === "approved" ? "approved" : "review"}`}>{t.approval_label_ar}</span>
      </div>
      {t.suitability_ar && (
        <div style={{ marginTop: 4 }}>
          <span className={`badge ${t.suitability === "high" ? "approved" : t.suitability === "medium" ? "agent" : "muted"}`}>
            درجة الملاءمة: {t.suitability_ar}
          </span>
        </div>
      )}
      <p style={{ margin: "8px 0" }}>{t.method_ar}</p>
      {!compact && t.usage_ar && (
        <p style={{ margin: "6px 0" }}>
          <b>طريقة الاستخدام باختصار:</b> {t.usage_ar}
        </p>
      )}
      <div className="grid cols-2" style={{ gap: 8 }}>
        <div>
          <b>المواد</b>
          <ul style={{ margin: "4px 0", paddingInlineStart: 18 }}>{t.materials.map((m) => <li key={m}>{m}</li>)}</ul>
        </div>
        <div>
          <b>الأدوات</b>
          <ul style={{ margin: "4px 0", paddingInlineStart: 18 }}>{t.tools.map((m) => <li key={m}>{m}</li>)}</ul>
        </div>
      </div>
      {t.cautions_ar.length > 0 && (
        <div className="banner warn" style={{ margin: "6px 0" }}>
          <b>تحذيرات:</b>
          <ul>{t.cautions_ar.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      )}
      <SourceList t={t} max={compact ? 1 : 3} />
      <small className="muted">توصية أولية وتحتاج إلى اعتماد مختص الترميم.</small>
    </div>
  );
}
