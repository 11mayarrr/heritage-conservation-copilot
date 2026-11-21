import { describe, expect, it } from "vitest";
import { joinList, splitList } from "./lists";

describe("materials and tools lists", () => {
  it("keeps an item whole when it contains commas inside parentheses", () => {
    const items = ["مونة طينية جديدة (طين، رمل، ماء، وقد يضاف تبن)", "ماء للرش الخفيف"];
    expect(splitList(joinList(items))).toEqual(items);
  });

  it("keeps ASCII commas inside an item", () => {
    const items = ["clay, sand and water mix", "trowel"];
    expect(splitList(joinList(items))).toEqual(items);
  });

  it("trims spaces, drops blank lines and accepts Windows line endings", () => {
    expect(splitList("  مالج  \r\n\r\n رشاش ماء \n")).toEqual(["مالج", "رشاش ماء"]);
  });

  it("returns an empty list for empty text", () => {
    expect(splitList("")).toEqual([]);
    expect(joinList([])).toBe("");
  });
});
