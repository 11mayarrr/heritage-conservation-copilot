import { describe, expect, it } from "vitest";
import { APPROVE_ONLY_HINT, canApprove } from "./auth";

describe("canApprove", () => {
  it("allows only the specialist role", () => {
    expect(canApprove("specialist")).toBe(true);
    expect(canApprove("assistant")).toBe(false);
  });
  it("denies when nobody is signed in", () => {
    expect(canApprove(null)).toBe(false);
    expect(canApprove(undefined)).toBe(false);
  });
  it("explains the rule in Arabic", () => {
    expect(APPROVE_ONLY_HINT).toContain("للمختص");
  });
});
