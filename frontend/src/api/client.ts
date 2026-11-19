import type {
  AuditEntry,
  Comparison,
  Health,
  Inspection,
  KnowledgeSource,
  Region,
  Retrieval,
  Treatment,
  WallSummary,
} from "./types";

const USER_KEY = "hcc.user";

export function getUserName(): string {
  try {
    return localStorage.getItem(USER_KEY) || "مختص تجريبي";
  } catch {
    return "مختص تجريبي";
  }
}

export function setUserName(name: string): void {
  try {
    localStorage.setItem(USER_KEY, name);
  } catch {
    /* storage unavailable: name lasts for this page only */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-User-Name", encodeURIComponent(getUserName()));
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    let msg = `خطأ ${res.status}`;
    try {
      const data = await res.json();
      msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  health: () => request<Health>("/api/health"),

  walls: () => request<WallSummary[]>("/api/walls"),
  createWall: (code: string, building_name: string, location_note = "") =>
    request<WallSummary>("/api/walls", { method: "POST", body: json({ code, building_name, location_note }) }),

  inspections: () => request<Inspection[]>("/api/inspections"),
  inspection: (id: string) => request<Inspection>(`/api/inspections/${id}`),
  upload: (wallId: string, file: File, capturedAt?: string) => {
    const fd = new FormData();
    fd.append("wall_id", wallId);
    fd.append("image", file);
    if (capturedAt) fd.append("captured_at", capturedAt);
    return request<Inspection>("/api/inspections", { method: "POST", body: fd });
  },
  setNotes: (id: string, expert_notes: string) =>
    request<Inspection>(`/api/inspections/${id}/notes`, { method: "PUT", body: json({ expert_notes }) }),
  approve: (id: string, reason = "") =>
    request<Inspection>(`/api/inspections/${id}/approve`, { method: "POST", body: json({ reason }) }),
  returnForReview: (id: string, reason = "") =>
    request<Inspection>(`/api/inspections/${id}/return`, { method: "POST", body: json({ reason }) }),
  reanalyze: (id: string) => request<Inspection>(`/api/inspections/${id}/reanalyze`, { method: "POST" }),
  manualBlur: (id: string, boxes: number[][], reason = "") =>
    request<Inspection>(`/api/inspections/${id}/blur`, { method: "POST", body: json({ boxes, reason }) }),

  addRegion: (id: string, body: Partial<Region> & { reason?: string }) =>
    request<Region>(`/api/inspections/${id}/regions`, { method: "POST", body: json(body) }),
  updateRegion: (id: string, rid: string, body: Partial<Region> & { reason?: string }) =>
    request<Region>(`/api/inspections/${id}/regions/${rid}`, { method: "PATCH", body: json(body) }),
  deleteRegion: (id: string, rid: string, reason = "") =>
    request<void>(`/api/inspections/${id}/regions/${rid}?reason=${encodeURIComponent(reason)}`, { method: "DELETE" }),
  approveRegion: (id: string, rid: string, reason = "") =>
    request<Region>(`/api/inspections/${id}/regions/${rid}/approve`, { method: "POST", body: json({ reason }) }),
  returnRegion: (id: string, rid: string, reason = "") =>
    request<Region>(`/api/inspections/${id}/regions/${rid}/return`, { method: "POST", body: json({ reason }) }),

  knowledge: () => request<{ treatments: Treatment[]; sources: KnowledgeSource[] }>("/api/knowledge"),
  retrieve: (damageType: string, context = "") =>
    request<Retrieval>(`/api/knowledge/retrieve?damage_type=${damageType}&context=${encodeURIComponent(context)}`),

  audit: (inspectionId?: string) =>
    request<AuditEntry[]>(`/api/audit${inspectionId ? `?inspection_id=${inspectionId}` : ""}`),

  comparisons: (wallId?: string) => request<Comparison[]>(`/api/comparisons${wallId ? `?wall_id=${wallId}` : ""}`),
  compare: (before_id: string, after_id: string) =>
    request<Comparison>("/api/comparisons", { method: "POST", body: json({ before_id, after_id }) }),
};

export const urls = {
  image: (id: string, download = false) => `/api/inspections/${id}/image.jpg${download ? "?download=true" : ""}`,
  atlas: (id: string, download = false) => `/api/inspections/${id}/atlas.png${download ? "?download=true" : ""}`,
  report: (id: string, download = false) => `/api/inspections/${id}/report.html${download ? "?download=true" : ""}`,
  comparisonImage: (cid: string, name: "side_by_side" | "after_aligned") => `/api/comparisons/${cid}/${name}.jpg`,
};
