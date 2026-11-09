import { api } from "./base";

export interface ModelParam {
  key: string;
  label: string;
  type: "int" | "float";
  default: number;
}

export interface ModelDef {
  id: string;
  label: string;
  params: ModelParam[];
}

export interface FrameworkModels {
  alpha: ModelDef[];
  portfolio_construction: ModelDef[];
  risk: ModelDef[];
}

export async function fetchFrameworkModels(): Promise<FrameworkModels> {
  const { data } = await api.get<FrameworkModels>("/framework/models");
  return data;
}

export interface ModelSpec {
  id: string;
  params: Record<string, number>;
}

export interface FrameworkBacktestRequest {
  tickers: string[];
  start?: string | null;
  end?: string | null;
  benchmark?: string | null;
  rebalance_freq: string;
  initial_cash: number;
  transaction_cost_bps: number;
  top_n: number;
  long_only: boolean;
  alpha: ModelSpec;
  portfolio_construction: ModelSpec;
  risk: ModelSpec[];
}

export interface EquityPoint {
  date: string;
  strategy: number;
  benchmark: number | null;
}

export interface FrameworkBacktestResult {
  summary: {
    strategy: Record<string, number>;
    benchmark: Record<string, number> | null;
    alpha_total_return: number;
  };
  equity_curve: EquityPoint[];
  holdings: {
    rebalance_date: string;
    weights: Record<string, number>;
    turnover: number;
  }[];
  insights: {
    date: string;
    symbol: string;
    direction: number;
    confidence: number;
    magnitude: number;
  }[];
}

export async function runFrameworkBacktest(req: FrameworkBacktestRequest): Promise<FrameworkBacktestResult> {
  const { data } = await api.post<FrameworkBacktestResult>("/framework/backtest", req);
  return data;
}
