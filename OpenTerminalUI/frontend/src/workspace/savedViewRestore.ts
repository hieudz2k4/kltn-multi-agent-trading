import type { SavedViewPayload } from "../api/savedViews";

const PENDING_SAVED_VIEW_KEY = "ot:saved-view:pending";

export function consumePendingSavedView(pagePath: string): SavedViewPayload | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(PENDING_SAVED_VIEW_KEY);
    if (!raw) return null;
    const payload = JSON.parse(raw) as SavedViewPayload;
    if (!payload?.page || payload.page !== pagePath) return null;
    localStorage.removeItem(PENDING_SAVED_VIEW_KEY);
    return payload;
  } catch {
    localStorage.removeItem(PENDING_SAVED_VIEW_KEY);
    return null;
  }
}
