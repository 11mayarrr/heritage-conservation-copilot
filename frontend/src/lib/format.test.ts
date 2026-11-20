import { describe, expect, it } from "vitest";
import { DAMAGE } from "./constants";
import { polygonArea, shortValue } from "./format";

describe("format helpers", () => {
  it("computes normalized polygon area", () => {
    expect(polygonArea([[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]])).toBeCloseTo(0.25);
  });
  it("summarizes polygons in audit values", () => {
    expect(shortValue([[0, 0], [1, 0], [1, 1]])).toBe("مضلع (3 نقطة)");
    expect(shortValue(null)).toBe("—");
  });
});

describe("fixed atlas colors", () => {
  it("match the specification", () => {
    expect(DAMAGE.crack.color).toBe("#D32F2F");
    expect(DAMAGE.plaster_loss.color).toBe("#F57C00");
    expect(DAMAGE.moisture_erosion.color).toBe("#1E63B5");
    expect(DAMAGE.material_loss.color).toBe("#7B1FA2");
    expect(DAMAGE.uncertain.color).toBe("#8A8A8A");
  });
});
