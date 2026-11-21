import { describe, expect, it } from "vitest";
import type { Inspection } from "../api/types";
import { splitQualityNotes } from "./qualityNotes";

const base = { acceptable: true, sharpness: 100, brightness: 120, contrast: 40, issues: [] };

describe("splitQualityNotes", () => {
  it("shows a strong tilt as a banner and removes it from the muted notes", () => {
    const q: Inspection["quality"] = {
      ...base,
      warnings: ["وضوح متوسط.", "مائلة كثيرًا."],
      tilt: { status: "strong", angle_deg: 31, note_ar: "مائلة كثيرًا." },
    };
    expect(splitQualityNotes(q)).toEqual({ tiltBanner: "مائلة كثيرًا.", notes: ["وضوح متوسط."] });
  });

  it("keeps a partial or unmeasurable tilt in the muted notes only", () => {
    for (const status of ["partial", "unmeasurable"] as const) {
      const q: Inspection["quality"] = {
        ...base,
        warnings: ["ملاحظة الميل."],
        tilt: { status, angle_deg: null, note_ar: "ملاحظة الميل." },
      };
      expect(splitQualityNotes(q)).toEqual({ tiltBanner: null, notes: ["ملاحظة الميل."] });
    }
  });

  it("handles cases analysed before the tilt existed", () => {
    const q: Inspection["quality"] = { ...base, warnings: ["قديمة."] };
    expect(splitQualityNotes(q)).toEqual({ tiltBanner: null, notes: ["قديمة."] });
  });
});
