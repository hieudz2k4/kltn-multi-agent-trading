import { api } from "./base";
import type {
  ScreenerResponse,
  ScreenerRule,
  ScreenerFactorConfig,
  ScreenerV2Response,
  ScannerPreset,
  ScannerPresetPayload,
  ScannerResult,
  ScannerRun,
  ScreenerPresetV3,
  ScreenerRunRequestV3,
  ScreenerRunResponseV3,
  UserScreenV3,
  CustomFormulaRunRequest,
  CustomFormulaResponse,
  SavedFormula,
} from "../types";
import type {
  ScreenerScanRequest,
  ScreenerScanResponse,
} from "./types";

export async function runScreener(rules: ScreenerRule[], limit = 50): Promise<ScreenerResponse> {
  const { data } = await api.post<ScreenerResponse>("/screener/run", {
    rules,
    sort_by: "roe_pct",
    sort_order: "desc",
    limit,
    universe: "nse_eq",
  });
  return data;
}

export async function runScreenerV2(
  rules: ScreenerRule[],
  factors: ScreenerFactorConfig[],
  opts?: { limit?: number; sectorNeutral?: boolean; universe?: string }
): Promise<ScreenerV2Response> {
  const { data } = await api.post<ScreenerV2Response>("/screener/run-v2", {
    rules,
    factors,
    sort_order: "desc",
    limit: opts?.limit ?? 50,
    universe: opts?.universe ?? "nse_eq",
    sector_neutral: opts?.sectorNeutral ?? false,
  });
  return data;
}

export async function fetchScannerPresets(): Promise<ScannerPreset[]> {
  const { data } = await api.get<{ items: ScannerPreset[] }>("/v1/screener/presets");
  return Array.isArray(data?.items) ? data.items : [];
}

export async function createScannerPreset(payload: ScannerPresetPayload): Promise<ScannerPreset> {
  const { data } = await api.post<ScannerPreset>("/v1/screener/presets", payload);
  return data;
}

export async function updateScannerPreset(id: string, payload: ScannerPresetPayload): Promise<ScannerPreset> {
  const { data } = await api.put<ScannerPreset>(`/v1/screener/presets/${encodeURIComponent(id)}`, payload);
  return data;
}

export async function deleteScannerPreset(id: string): Promise<void> {
  await api.delete(`/v1/screener/presets/${encodeURIComponent(id)}`);
}

export async function runScanner(payload: { preset_id?: string; inline_preset?: ScannerPresetPayload; limit?: number; offset?: number }): Promise<{
  run_id: string;
  count: number;
  rows: Array<Record<string, unknown>>;
  summary: Record<string, unknown>;
}> {
  const { data } = await api.post("/v1/screener/run", payload, { timeout: 120000 });
  return data;
}

export async function fetchScannerRuns(limit = 20, offset = 0): Promise<ScannerRun[]> {
  const { data } = await api.get<{ items: ScannerRun[] }>("/v1/screener/runs", { params: { limit, offset } });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchScannerResults(runId: string, limit = 100, offset = 0): Promise<ScannerResult[]> {
  const { data } = await api.get<{ items: ScannerResult[] }>("/v1/screener/results", { params: { run_id: runId, limit, offset } });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchScreenerPresetsV3(): Promise<ScreenerPresetV3[]> {
  const { data } = await api.get<{ items: ScreenerPresetV3[] }>("/screener/presets");
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchScreenerPresetV3(id: string): Promise<ScreenerPresetV3> {
  const { data } = await api.get<ScreenerPresetV3>(`/screener/presets/${encodeURIComponent(id)}`);
  return data;
}

export async function runScreenerV3(payload: ScreenerRunRequestV3): Promise<ScreenerRunResponseV3> {
  const { data } = await api.post<ScreenerRunResponseV3>("/screener/run-revamped", payload, { timeout: 120000 });
  return data;
}

export async function fetchScreenerFieldsV3(): Promise<Array<Record<string, string>>> {
  const { data } = await api.get<{ items: Array<Record<string, string>> }>("/screener/fields");
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchScreenerUniversesV3(): Promise<Array<{ id: string; name: string }>> {
  const { data } = await api.get<{ items: Array<{ id: string; name: string }> }>("/screener/universes");
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchSavedScreensV3(): Promise<UserScreenV3[]> {
  const { data } = await api.get<{ items: UserScreenV3[] }>("/screener/screens");
  return Array.isArray(data?.items) ? data.items : [];
}

export async function createSavedScreenV3(payload: {
  name: string;
  description?: string;
  query: string;
  columns_config?: string[];
  viz_config?: Record<string, unknown>;
  is_public?: boolean;
}): Promise<UserScreenV3> {
  const { data } = await api.post<UserScreenV3>("/screener/screens", payload);
  return data;
}

export async function updateSavedScreenV3(
  id: string,
  payload: {
    name: string;
    description?: string;
    query: string;
    columns_config?: string[];
    viz_config?: Record<string, unknown>;
    is_public?: boolean;
  },
): Promise<UserScreenV3> {
  const { data } = await api.put<UserScreenV3>(`/screener/screens/${encodeURIComponent(id)}`, payload);
  return data;
}

export async function deleteSavedScreenV3(id: string): Promise<void> {
  await api.delete(`/screener/screens/${encodeURIComponent(id)}`);
}

export async function fetchPublicScreensV3(limit = 50, offset = 0): Promise<UserScreenV3[]> {
  const { data } = await api.get<{ items: UserScreenV3[] }>("/screener/public", { params: { limit, offset } });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function runCustomFormulaScreener(payload: CustomFormulaRunRequest): Promise<CustomFormulaResponse> {
  const { data } = await api.post<CustomFormulaResponse>("/screener/custom-formula", payload, { timeout: 120000 });
  return data;
}

export async function fetchSavedFormulas(): Promise<SavedFormula[]> {
  const { data } = await api.get<SavedFormula[]>("/screener/saved-formulas");
  return Array.isArray(data) ? data : [];
}

export async function createSavedFormula(payload: {
  name: string;
  formula: string;
  description?: string;
}): Promise<SavedFormula> {
  const { data } = await api.post<SavedFormula>("/screener/saved-formulas", payload);
  return data;
}

export async function deleteSavedFormula(id: number): Promise<void> {
  await api.delete(`/screener/saved-formulas/${id}`);
}

export async function publishScreenV3(id: string): Promise<UserScreenV3> {
  const { data } = await api.post<UserScreenV3>(`/screener/screens/${encodeURIComponent(id)}/publish`);
  return data;
}

export async function forkPublicScreenV3(id: string): Promise<UserScreenV3> {
  const { data } = await api.post<UserScreenV3>(`/screener/screens/${encodeURIComponent(id)}/fork`);
  return data;
}

export async function exportScreenerV3(
  format: "csv" | "xlsx" | "pdf",
  payload: { rows: Array<Record<string, unknown>>; columns?: string[]; title?: string },
): Promise<Blob> {
  const { data } = await api.post(`/screener/export/${format}`, payload, { responseType: "blob" });
  return data as Blob;
}

export async function runScreenerScan(payload: ScreenerScanRequest): Promise<ScreenerScanResponse> {
  const { data } = await api.post<ScreenerScanResponse>("/screener/scan", payload, { timeout: 120000 });
  return data;
}
