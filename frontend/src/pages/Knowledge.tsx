import { useState } from "react";
import { api } from "../api/client";
import type { DamageType } from "../api/types";
import { DamageLabel } from "../components/Badges";
import { TreatmentCard } from "../components/TreatmentCard";
import { DAMAGE, DAMAGE_TYPES } from "../lib/constants";
import { useAsync } from "../lib/useAsync";

export default function Knowledge() {
  const { data, error } = useAsync(() => api.knowledge(), []);
  const [type, setType] = useState<DamageType | "all">("all");
  const list = (data?.treatments ?? []).filter((t) => type === "all" || t.damage_types.includes(type));

  return (
    <>
      <h1>قاعدة المعرفة</h1>
      <div className="banner warn">
        مكتبة مغلقة: لا يقترح الوكيل إلا ما هو موجود هنا. المحتوى الحالي تجريبي مأخوذ من مصدر عام موثوق، ولا يغني عن مكتبة المعالجات
        المعتمدة من الجهة المختصة. لإضافة معالجات: <code>knowledge_base/*.json</code>.
      </div>
      {error && <div className="banner danger">{error}</div>}
      <div className="card">
        <h2>المصادر</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>المصدر</th><th>الناشر</th><th>السنة</th><th>الحالة</th><th>ملاحظة</th></tr></thead>
            <tbody>
              {data?.sources.map((s) => (
                <tr key={s.id}>
                  <td><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>{s.authors && <><br /><small>{s.authors}</small></>}</td>
                  <td>{s.publisher}</td>
                  <td>{s.year}</td>
                  <td><span className={`badge ${s.status === "read" ? "approved" : "muted"}`}>{s.status === "read" ? "مقروء ومستخدم" : "غير مقروء — لا يُستشهد به"}</span></td>
                  <td><small>{s.context_note_ar}</small></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <div className="toolbar" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>المعالجات ({list.length})</h2>
          <select value={type} onChange={(e) => setType(e.target.value as DamageType | "all")} style={{ width: "auto" }}>
            <option value="all">كل أنواع التلف</option>
            {DAMAGE_TYPES.map((t) => <option key={t} value={t}>{DAMAGE[t].label}</option>)}
          </select>
        </div>
        {type === "uncertain" && <div className="banner info" style={{ marginTop: 8 }}>لا تُقترح معالجة لتلف غير مؤكد قبل الفحص الميداني.</div>}
        <div className="grid cols-2" style={{ marginTop: 10 }}>
          {list.map((t) => (
            <div key={t.id}>
              <div className="chips" style={{ marginBottom: 4 }}>{t.damage_types.map((d) => <span className="chip" key={d}><DamageLabel type={d} /></span>)}</div>
              <TreatmentCard t={t} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
