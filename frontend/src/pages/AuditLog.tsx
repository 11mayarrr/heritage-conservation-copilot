import { useState } from "react";
import { api } from "../api/client";
import { ACTION_LABEL, FIELD_LABEL } from "../lib/constants";
import { formatDate, shortValue } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function AuditLog() {
  const inspections = useAsync(() => api.inspections(), []);
  const [inspectionId, setInspectionId] = useState("");
  const { data, error, loading } = useAsync(() => api.audit(inspectionId || undefined), [inspectionId]);
  const caseOf = new Map((inspections.data ?? []).map((i) => [i.id, i.case_number]));

  return (
    <>
      <h1>سجل التعديلات</h1>
      <div className="card">
        <label style={{ maxWidth: 360 }}>
          تصفية حسب الحالة
          <select value={inspectionId} onChange={(e) => setInspectionId(e.target.value)}>
            <option value="">كل الحالات</option>
            {inspections.data?.map((i) => <option key={i.id} value={i.id}>{i.case_number} — {i.wall.code}</option>)}
          </select>
        </label>
        {error && <div className="banner danger">{error}</div>}
        {loading && <span className="spinner" />}
        <div className="table-wrap">
          <table>
            <thead><tr><th>الوقت</th><th>المستخدم</th><th>الحالة</th><th>العنصر</th><th>الإجراء</th><th>الحقل</th><th>القيمة القديمة</th><th>القيمة الجديدة</th><th>السبب</th></tr></thead>
            <tbody>
              {data?.map((e) => (
                <tr key={e.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{formatDate(e.at, true)}</td>
                  <td>{e.user}</td>
                  <td>{e.inspection_id ? caseOf.get(e.inspection_id) ?? "—" : "—"}</td>
                  <td>{e.entity}</td>
                  <td>{ACTION_LABEL[e.action] ?? e.action}</td>
                  <td>{e.field ? FIELD_LABEL[e.field] ?? e.field : "—"}</td>
                  <td>{shortValue(e.old_value)}</td>
                  <td>{shortValue(e.new_value)}</td>
                  <td>{e.reason || "—"}</td>
                </tr>
              ))}
              {data?.length === 0 && <tr><td colSpan={9} className="empty">لا توجد سجلات.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
