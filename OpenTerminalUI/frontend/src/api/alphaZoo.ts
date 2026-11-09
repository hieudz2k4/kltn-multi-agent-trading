import { api } from "./base";

export type AlphaZooSummary = {
  id: string;
  name: string;
  source: string;
  count: number;
};

export type AlphaFactor = {
  id: string;
  name: string;
  zoo: string;
  category: string;
  description: string;
  window: number;
};

export type AlphaZooFactorsResponse = {
  zoos: AlphaZooSummary[];
  factors: AlphaFactor[];
};

export type AlphaEvaluateRequest = {
  symbols: string[];
  factor_ids?: string[];
  zoo?: string;
  range?: string;
  forward_days?: number;
};

export type AlphaResultStatus = "alive" | "reversed" | "dead" | "insufficient";

export type AlphaEvaluateResult = {
  factor_id: string;
  name: string;
  zoo: string;
  category: string;
  ic: number;
  ir: number;
  rank_ic: number;
  hit_rate: number;
  status: AlphaResultStatus;
  values: Record<string, number | null>;
};

export type AlphaEvaluateResponse = {
  as_of: string;
  symbols: string[];
  coverage: {
    requested: number;
    resolved: number;
    missing: string[];
  };
  results: AlphaEvaluateResult[];
};

export async function fetchAlphaZooFactors(): Promise<AlphaZooFactorsResponse> {
  const { data } = await api.get<AlphaZooFactorsResponse>("/alpha-zoo/factors");
  return data;
}

export async function evaluateAlphaZoo(payload: AlphaEvaluateRequest): Promise<AlphaEvaluateResponse> {
  const { data } = await api.post<AlphaEvaluateResponse>("/alpha-zoo/evaluate", payload);
  return data;
}
