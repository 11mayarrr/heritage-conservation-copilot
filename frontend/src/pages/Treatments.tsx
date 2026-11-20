import { useParams } from "react-router-dom";
import { api } from "../api/client";
import type { DamageType, Retrieval } from "../api/types";
import { DamageLabel, RegionFlags } from "../components/Badges";
import { InspectionPicker } from "../components/InspectionPicker";
import { MaterialsByLocation } from "../components/MaterialsByLocation";
import { StepTracker } from "../components/StepTracker";
import { PreliminaryNotice } from "../components/Notices";
import { TreatmentCard } from "../components/TreatmentCard";
import { INSUFFICIENT_AR } from "../lib/constants";
import { useAsync } from "../lib/useAsync";

export default function Treatments() {
  const { id } = useParams();
  if (!id) return <InspectionPicker basePath="/treatments" title="المعالجة والمواد" />;
  return <TreatmentsView id={id} />;
}

function TreatmentsView({ id }: { id: string }) {
  const { data, error } = useAsync(async () => {
    const insp = await api.inspection(id);
    const types = [...new Set(insp.regions.map((r) => r.damage_type))];
    const retrievals: Record<string, Retrieval> = {};
    await Promise.all(types.map(async (t) => {
      const ctx = insp.regions.filter((r) => r.damage_type === t).map((r) => `${r.description} ${r.note}`).join(" ");
      retrievals[t] = await api.retrieve(t, ctx);
    }));
    const kb = await api.knowledge();
    return { insp, retrievals, kb };
  }, [id]);

  if (error) return <div className="banner danger">{error}</div>;
  if (!data) return <span className="spinner" />;
  const { insp, retrievals, kb } = data;
  const byId = new Map(kb.treatments.map((t) => [t.id, t]));

  return (
    <>
      <h1>المعالجة والمواد — {insp.case_number}</h1>
      <StepTracker insp={insp} />
      <PreliminaryNotice />
      <div className="card">
        <h2>ربط المناطق بالمعالجات</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>المنطقة</th><th>النوع</th><th>الموقع</th><th>رمز المعالجة</th><th>المعالجة المرتبطة</th><th>المواد</th><th>الأدوات</th><th>المصدر</th><th>الحالة</th></tr></thead>
            <tbody>
              {insp.regions.map((r) => {
                const t = r.treatment_id ? byId.get(r.treatment_id) : undefined;
                return (
                  <tr key={r.id}>
                    <td><b>R{r.index}</b></td>
                    <td><DamageLabel type={r.damage_type} /></td>
                    <td>{r.grid_cells.join("، ")}</td>
                    <td>{t ? <code dir="ltr">{t.id}</code> : "—"}</td>
                    <td>{t ? t.title_ar : <span className="muted">{INSUFFICIENT_AR}</span>}</td>
                    <td>{r.materials.join("، ") || "—"}</td>
                    <td>{r.tools.join("، ") || "—"}</td>
                    <td>{t ? <small>{t.sources[0]?.title} — <span dir="ltr">{t.sources[0]?.locator}</span></small> : "—"}</td>
                    <td><RegionFlags r={r} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <MaterialsByLocation rows={insp.materials_by_location} />

      {Object.entries(retrievals).map(([type, ret]) => (
        <div className="card" key={type}>
          <h2><DamageLabel type={type as DamageType} /></h2>
          {!ret.sufficient && <div className="banner warn">{ret.message_ar}</div>}
          <div className="grid cols-2">
            {ret.results.map((t) => <TreatmentCard key={t.id} t={t} />)}
          </div>
        </div>
      ))}
    </>
  );
}
