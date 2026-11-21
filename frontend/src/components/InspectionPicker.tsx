import { Link } from "react-router-dom";
import { api } from "../api/client";
import { formatDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { InspectionStatusBadge } from "./Badges";

/** Shown by inspection-scoped pages when no case is selected. */
export function InspectionPicker({ basePath, title }: { basePath: string; title: string }) {
  const { data, loading, error } = useAsync(() => api.inspections(), []);
  const usable = (data ?? []).filter((i) => i.has_image);
  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="muted">اختر حالة فحص لفتحها.</p>
      {loading && <span className="spinner" />}
      {error && <div className="banner danger">{error}</div>}
      {!loading && usable.length === 0 && (
        <div className="empty">
          لا توجد حالات بعد. <Link to="/upload">ارفع صورة جدار</Link>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <tbody>
            {usable.map((i) => (
              <tr key={i.id}>
                <td><Link to={`${basePath}/${i.id}`}>{i.case_number}</Link></td>
                <td>جدار {i.wall.code}</td>
                <td>{formatDate(i.captured_at)}</td>
                <td>{i.summary.total} منطقة</td>
                <td><InspectionStatusBadge status={i.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
