import { useState } from "react";
import { api } from "../api/client";
import type { Inspection } from "../api/types";
import { gridOutdated, gridSummary } from "./GridEditor";

/** Shown when the wall's reference grid changed after this case was analysed. */
export function GridOutdatedNotice({ insp, onApplied }: { insp: Inspection; onApplied: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const wallGrid = insp.wall.grid;
  if (!wallGrid || !gridOutdated(insp.grid, wallGrid)) return null;
  const locked = insp.status === "approved";

  const apply = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.applyWallGrid(insp.id);
      onApplied();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="banner warn">
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <span>
          حُللت هذه الحالة بشبكة <b>{gridSummary(insp.grid)}</b>، والشبكة الحالية للجدار <b>{gridSummary(wallGrid)}</b>.
          {locked && " الحالة معتمدة فتبقى بشبكتها الأصلية."}
        </span>
        {!locked && (
          <button disabled={busy} onClick={apply}>
            {busy ? <span className="spinner" /> : null} تطبيق شبكة الجدار على هذه الحالة
          </button>
        )}
      </div>
      {err && <div>{err}</div>}
    </div>
  );
}
