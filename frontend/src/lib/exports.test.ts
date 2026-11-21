import { describe, expect, it } from "vitest";
import type { InspectionStatus } from "../api/types";
import { canExport } from "./exports";

describe("canExport", () => {
  it("allows only approved inspections", () => {
    expect(canExport("approved")).toBe(true);
  });

  it("refuses every other status", () => {
    const others: InspectionStatus[] = ["in_review", "returned", "rejected_quality"];
    for (const status of others) expect(canExport(status)).toBe(false);
  });
});
