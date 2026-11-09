import { api } from "./base";
import type {
  RiskPortfolioResponse,
} from "../types";

export async function fetchPortfolioRisk(payload: {
  symbols?: string[];
  weights?: number[];
  confidence?: number;
  lookback_days?: number;
  portfolio_value?: number;
}): Promise<RiskPortfolioResponse> {
  const { data } = await api.post<RiskPortfolioResponse>("/risk/portfolio", payload);
  return data;
}

export async function fetchBacktestRisk(runId: string, confidence = 0.95): Promise<RiskPortfolioResponse> {
  const { data } = await api.post<RiskPortfolioResponse>(`/risk/backtest/${encodeURIComponent(runId)}?confidence=${confidence}`, {});
  return data;
}

export async function fetchRiskScenarios(): Promise<Array<Record<string, unknown>>> {
  const { data } = await api.get<{ items: Array<Record<string, unknown>> }>("/risk/scenarios");
  return Array.isArray(data?.items) ? data.items : [];
}
