import { api } from "./base";

export type StrategyPreset = {
  id: string;
  name: string;
  description: string;
  spec: unknown;
};

export type StrategyPresetsResponse = {
  presets: StrategyPreset[];
};

export type StrategyExportFormat = "pine" | "mql5";

export type StrategyGenerateRequest = {
  spec: unknown;
  format: StrategyExportFormat;
};

export type StrategyGenerateResponse = {
  code: string;
  language: string;
  filename: string;
  warnings: string[];
};

export async function fetchStrategyPresets(): Promise<StrategyPresetsResponse> {
  const { data } = await api.get<StrategyPresetsResponse>("/strategy-export/presets");
  return data;
}

export async function generateStrategy(payload: StrategyGenerateRequest): Promise<StrategyGenerateResponse> {
  const { data } = await api.post<StrategyGenerateResponse>("/strategy-export/generate", payload);
  return data;
}
