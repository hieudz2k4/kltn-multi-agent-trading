import { api } from "./base";
import type { RebalanceFrequency, WeightingMethod, PortfolioDefinition, StrategyBlend, PortfolioRunStatus, PortfolioReport } from "./types";

export async function createPortfolioDefinition(payload: {
  name: string;
  description?: string;
  tags?: string[];
  universe_json: Record<string, unknown>;
  benchmark_symbol?: string;
  start_date: string;
  end_date: string;
  rebalance_frequency: RebalanceFrequency;
  weighting_method: WeightingMethod;
  constraints_json?: Record<string, unknown>;
}): Promise<PortfolioDefinition> {
  const { data } = await api.post<PortfolioDefinition>("/portfolio-lab/portfolios", payload);
  return data;
}

export async function listPortfolioDefinitions(params?: { tag?: string; weighting_method?: WeightingMethod }): Promise<PortfolioDefinition[]> {
  const { data } = await api.get<{ items: PortfolioDefinition[] }>("/portfolio-lab/portfolios", { params });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function getPortfolioDefinition(id: string): Promise<PortfolioDefinition & {
  universe_json: Record<string, unknown>;
  constraints_json: Record<string, unknown>;
  runs: PortfolioRunStatus[];
}> {
  const { data } = await api.get<PortfolioDefinition & { universe_json: Record<string, unknown>; constraints_json: Record<string, unknown>; runs: PortfolioRunStatus[] }>(`/portfolio-lab/portfolios/${encodeURIComponent(id)}`);
  return data;
}

export async function createStrategyBlend(payload: {
  name: string;
  strategies_json: StrategyBlend["strategies_json"];
  blend_method: StrategyBlend["blend_method"];
}): Promise<StrategyBlend> {
  const { data } = await api.post<StrategyBlend>("/portfolio-lab/blends", payload);
  return data;
}

export async function listStrategyBlends(): Promise<StrategyBlend[]> {
  const { data } = await api.get<{ items: StrategyBlend[] }>("/portfolio-lab/blends");
  return Array.isArray(data?.items) ? data.items : [];
}

export async function runPortfolioDefinition(portfolioId: string, payload?: { blend_id?: string; force_refresh?: boolean }): Promise<PortfolioRunStatus> {
  const { data } = await api.post<PortfolioRunStatus>(`/portfolio-lab/portfolios/${encodeURIComponent(portfolioId)}/run`, payload || {});
  return data;
}

export async function getPortfolioRunStatus(runId: string): Promise<PortfolioRunStatus> {
  const { data } = await api.get<PortfolioRunStatus>(`/portfolio-lab/runs/${encodeURIComponent(runId)}`);
  return data;
}

export async function getPortfolioRunReport(runId: string, forceRefresh = false): Promise<PortfolioReport> {
  const { data } = await api.get<PortfolioReport>(`/portfolio-lab/runs/${encodeURIComponent(runId)}/report`, {
    params: { force_refresh: forceRefresh },
    timeout: 120000,
  });
  return data;
}
