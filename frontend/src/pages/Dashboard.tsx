import { Link } from "react-router-dom";
import { api } from "../api/client";
import { InspectionStatusBadge, Legend } from "../components/Badges";
import { DetectorNotice, PrivacyNotice } from "../components/Notices";
import { formatDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Dashboard() {
  const { data, loading, error } = useAsync(
    () => Promise.all([api.health(), api.inspections(), api.walls()]),
    [],
  );
  const [health, inspections, walls] = data ?? [null, [], []];
  const all = inspections ?? [];
  const regions = all.flatMap((i) => i.regions);
  const stats = [
    { l: "الجدران المسجلة", v: walls?.length ?? 0 },
    { l: "حالات الفحص", v: all.length },
    { l: "قيد المراجعة", v: all.filter((i) => i.status === "in_review" || i.status === "returned").length },
    { l: "حالات معتمدة", v: all.filter((i) => i.status === "approved").length },
    { l: "مناطق منخفضة الثقة", v: regions.filter((r) => r.low_confidence).length },
    { l: "مناطق تحتاج فحصًا ميدانيًا", v: regions.filter((r) => r.needs_field_inspection).length },
  ];

  return (
    <>
      <div className="topbar">
        <div>
          <h1>لوحة التحكم</h1>
          <small className="muted">حي الطريف، الدرعية — نموذج أولي لدعم قرارات ترميم الجدران الطينية</small>
        </div>
        <Link to="/upload" className="btn primary">رفع صورة جدار</Link>
      </div>
      {error && <div className="banner danger">تعذر الاتصال بالخادم: {error}</div>}
      <DetectorNotice detector={health?.detector} />
      <div className="grid cols-3" style={{ marginBottom: 14 }}>
        {stats.map((s) => (
          <div className="stat" key={s.l}>
            <div className="v">{loading ? "…" : s.v}</div>
            <div className="l">{s.l}</div>
          </div>
        ))}
      </div>
      <div className="grid cols-2">
        <div className="card">
          <h2>آخر حالات الفحص</h2>
          {all.length === 0 && !loading && <div className="empty">لا توجد حالات بعد.</div>}
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>الحالة</th><th>الجدار</th><th>التاريخ</th><th>المناطق</th><th>الاعتماد</th></tr>
              </thead>
              <tbody>
                {all.slice(0, 10).map((i) => (
                  <tr key={i.id}>
                    <td>{i.has_image ? <Link to={`/atlas/${i.id}`}>{i.case_number}</Link> : i.case_number}</td>
                    <td>{i.wall.code}</td>
                    <td>{formatDate(i.captured_at)}</td>
                    <td>{i.summary.total}</td>
                    <td><InspectionStatusBadge status={i.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card">
          <h2>سير العمل</h2>
          <ol style={{ margin: 0, paddingInlineStart: 20 }}>
            <li>رفع صورة حديثة وربطها برقم الجدار.</li>
            <li>فحص الجودة، وطلب إعادة التصوير عند الحاجة.</li>
            <li>إخفاء الوجوه قبل أي تحليل أو تخزين.</li>
            <li>تحديد مناطق التلف وتصنيفها وتقدير الثقة.</li>
            <li>استرجاع المعالجة والمواد والأدوات من قاعدة المعرفة.</li>
            <li>مراجعة المختص وتصحيحه، ثم الاعتماد.</li>
            <li>إصدار التقرير والخريطة، وحفظ سجل التعديلات.</li>
          </ol>
          <h3 style={{ marginTop: 12 }}>مفتاح الألوان</h3>
          <Legend />
        </div>
      </div>
      <div style={{ marginTop: 14 }}>
        <PrivacyNotice />
      </div>
    </>
  );
}
