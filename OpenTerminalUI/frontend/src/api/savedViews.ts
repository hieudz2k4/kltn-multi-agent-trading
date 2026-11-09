import { api } from "./base";

export type SavedViewPayload = {
  page: string;
  filters?: Record<string, unknown>;
  selectedTicker?: string;
  activeTabs?: Record<string, unknown>;
  tableColumns?: unknown;
  chartLayout?: unknown;
  shellPreset?: string;
  storage?: Record<string, unknown>;
  search?: string;
};

export type SavedView = {
  id: string;
  user_id: string;
  name: string;
  scope: string;
  page: string;
  payload: SavedViewPayload;
  description: string;
  created_at: string;
  updated_at: string;
};

export async function listSavedViews(params?: { scope?: string; page?: string }): Promise<SavedView[]> {
  const { data } = await api.get<{ items?: SavedView[] }>("/saved-views", { params });
  return data.items ?? [];
}

export async function createSavedView(payload: {
  name: string;
  scope: string;
  page: string;
  payload: SavedViewPayload;
  description?: string;
}): Promise<SavedView> {
  const { data } = await api.post<SavedView>("/saved-views", payload);
  return data;
}

export async function updateSavedView(id: string, payload: Partial<Pick<SavedView, "name" | "scope" | "page" | "description">> & { payload?: SavedViewPayload }): Promise<SavedView> {
  const { data } = await api.patch<SavedView>(`/saved-views/${id}`, payload);
  return data;
}

export async function deleteSavedView(id: string): Promise<void> {
  await api.delete(`/saved-views/${id}`);
}
