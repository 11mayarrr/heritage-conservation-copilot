import type { Role } from "../api/types";

/** Fired by the API client when the server answers 401 (not signed in / session ended). */
export const UNAUTHORIZED_EVENT = "hcc:unauthorized";

/** Only a specialist (مختص) may approve. The server enforces this too; the UI just
 *  avoids offering buttons that would be refused. */
export function canApprove(role: Role | null | undefined): boolean {
  return role === "specialist";
}

export const APPROVE_ONLY_HINT = "الاعتماد للمختص فقط. حسابك بدور «مساعد»: يمكنك الرفع والتعديل، ويعتمد المختص.";
