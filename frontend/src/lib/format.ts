import type { Point } from "../api/types";

export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`;

export function formatDate(iso: string | null | undefined, withTime = false): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("ar-SA-u-ca-gregory-nu-latn", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

/** Shoelace area of a normalized polygon (fraction of the image). */
export function polygonArea(poly: Point[]): number {
  let a = 0;
  for (let i = 0; i < poly.length; i++) {
    const [x0, y0] = poly[i];
    const [x1, y1] = poly[(i + 1) % poly.length];
    a += x0 * y1 - x1 * y0;
  }
  return Math.abs(a) / 2;
}

export function shortValue(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v) && v.length && Array.isArray(v[0])) return `مضلع (${v.length} نقطة)`;
  if (typeof v === "object") return JSON.stringify(v).slice(0, 80);
  if (typeof v === "boolean") return v ? "نعم" : "لا";
  return String(v).slice(0, 80);
}

export const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
