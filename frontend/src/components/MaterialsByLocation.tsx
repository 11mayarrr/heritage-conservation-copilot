import type { MaterialLocation } from "../api/types";

/** Step 6 output: every material and tool, with the damage regions and grid cells it is used in. */
export function MaterialsByLocation({ rows }: { rows: MaterialLocation[] | undefined }) {
  const list = rows ?? [];
  return (
    <div className="card">
      <h2>المواد والأدوات حسب موقع التلف</h2>
      <small className="muted">مخرج الخطوة 6. يُجمع من المواد والأدوات المرتبطة بكل منطقة، ويتحدث مع أي تعديل للمختص.</small>
      {list.length === 0 ? (
        <div className="empty">لا توجد مواد أو أدوات مرتبطة بالمناطق بعد. اربط معالجة بمنطقة من الخريطة أو المراجعة.</div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr><th>النوع</th><th>البند</th><th>المناطق</th><th>المواقع على الشبكة</th></tr>
            </thead>
            <tbody>
              {list.map((m) => (
                <tr key={`${m.kind}:${m.name}`}>
                  <td>{m.kind === "material" ? "مادة" : "أداة"}</td>
                  <td>{m.name}</td>
                  <td>{m.regions.join("، ")}</td>
                  <td>{m.cells.join("، ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
