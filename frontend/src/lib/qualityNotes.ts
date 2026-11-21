import type { Inspection } from "../api/types";

type Quality = Inspection["quality"];

/**
 * A strong camera tilt gets its own visible banner; every other quality note
 * (including a partial or unmeasurable tilt) stays in the small muted line so
 * that mud-wall photos with few straight lines are not buried in banners.
 */
export function splitQualityNotes(q: Quality): { tiltBanner: string | null; notes: string[] } {
  const tilt = q.tilt;
  if (tilt?.status === "strong") {
    return { tiltBanner: tilt.note_ar, notes: q.warnings.filter((w) => w !== tilt.note_ar) };
  }
  return { tiltBanner: null, notes: q.warnings };
}
