import { useSearchParams } from "react-router-dom";
import { api, urls } from "../api/client";
import { InspectionStatusBadge } from "../components/Badges";
import { formatDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Reports() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("id");
  const { data, error } = useAsync(() => api.inspections(), []);
  const list = (data ?? []).filter((i) => i.has_image);

  return (
    <>
      <h1>التقارير</h1>
      {error && <div className="banner danger">{error}</div>}
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead><tr><th>الحالة</th><th>الجدار</th><th>التاريخ</th><th>الاعتماد</th><th>المخرجات</th></tr></thead>
            <tbody>
              {list.map((i) => (
                <tr key={i.id} className={`clickable${selected === i.id ? " selected" : ""}`} onClick={() => setParams({ id: i.id })}>
                  <td><b>{i.case_number}</b></td>
                  <td>{i.wall.code}</td>
                  <td>{formatDate(i.captured_at)}</td>
                  <td><InspectionStatusBadge status={i.status} /></td>
                  <td>
                    <div className="toolbar" onClick={(e) => e.stopPropagation()}>
                      <a className="btn" href={urls.report(i.id)} target="_blank" rel="noreferrer">فتح التقرير</a>
                      <a className="btn" href={urls.report(i.id, true)}>تنزيل HTML</a>
                      <a className="btn" href={urls.atlas(i.id, true)}>الخريطة PNG</a>
                      <a className="btn" href={urls.image(i.id, true)}>الصورة المخفية</a>
                    </div>
                  </td>
                </tr>
              ))}
              {list.length === 0 && <tr><td colSpan={5} className="empty">لا توجد حالات.</td></tr>}
            </tbody>
          </table>
        </div>
        <small className="muted">لحفظ التقرير بصيغة PDF: افتح التقرير ثم استخدم الطباعة في المتصفح واختر «حفظ كـ PDF».</small>
      </div>
      {selected && (
        <div className="card">
          <h2>معاينة التقرير</h2>
          <iframe title="التقرير" src={urls.report(selected)} style={{ width: "100%", height: "75vh", border: "1px solid var(--line)", borderRadius: 8, background: "#fff" }} />
        </div>
      )}
    </>
  );
}
