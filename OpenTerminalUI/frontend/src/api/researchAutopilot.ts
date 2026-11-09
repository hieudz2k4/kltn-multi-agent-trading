import { api } from "./base";

export type SignalKind = "alpha_factor" | "momentum";
export type SignalDirection = "long_only" | "long_short";
export type VerdictStatus = "accepted" | "rejected" | "inconclusive";

export type AlphaZooSummary = {
  id: string;
  name: string;
  source?: string;
  count?: number;
};

export type AlphaFactorOption = {
  id: string;
  name: string;
  zoo: string;
  category: string;
  description: string;
  window: number;
};

export type AlphaFactorsResponse = {
  zoos: AlphaZooSummary[];
  factors: AlphaFactorOption[];
};

export type HypothesisSpec = {
  statement: string;
  universe: string[];
  benchmark?: string;
  signal: {
    kind: SignalKind;
    factor_id?: string;
    lookback_days?: number;
    direction?: SignalDirection;
  };
  acceptance: {
    min_sharpe?: number;
    min_cagr?: number;
    max_drawdown?: number;
    min_psr?: number;
    min_hit_rate?: number;
    min_alpha?: number;
  };
  range?: string;
  rebalance_days?: number;
  top_quantile?: number;
  long_short?: boolean;
};

export type Coverage = {
  requested: number;
  resolved: number;
  missing: string[];
};

export type BacktestMetrics = {
  total_return: number;
  cagr: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  volatility: number;
  hit_rate: number;
  turnover: number;
};

export type CurvePoint = {
  date: string;
  value: number;
};

export type BacktestResult = {
  as_of: string;
  bars: number;
  rebalance_days: number;
  long_short: boolean;
  metrics: BacktestMetrics;
  equity_curve: CurvePoint[];
  benchmark_curve: CurvePoint[];
};

export type RegimeAttribution = {
  regime: string;
  days: number;
  avg_daily_return: number;
  total_return: number;
  contribution: number;
};

export type PeriodReturn = {
  date: string;
  return: number;
};

export type AttributionResult = {
  regime: RegimeAttribution[];
  top_periods: PeriodReturn[];
  worst_periods: PeriodReturn[];
  permutation: {
    trials: number;
    observed_sharpe: number;
    p_value: number;
    better_count: number;
  };
  factor_exposure: {
    alpha_annual: number;
    beta: number;
    r_squared: number;
  };
};

export type RobustnessResult = {
  psr: number;
  dsr: number;
  annual_sharpe: number;
  verdict: string;
  verdict_reasons: string[];
  [key: string]: unknown;
};

export type CriteriaResult = {
  name: string;
  target: number | string;
  actual: number | string;
  pass: boolean;
};

export type VerdictResult = {
  status: VerdictStatus;
  score: number;
  criteria_results: CriteriaResult[];
  reasons: string[];
};

export type RunResult = {
  run_id: string;
  hypothesis_id: string;
  coverage: Coverage;
  backtest: BacktestResult;
  attribution: AttributionResult;
  robustness: RobustnessResult;
  verdict: VerdictResult;
  signal: HypothesisSpec["signal"];
  universe: string[];
};

export type SavedHypothesis = {
  id: string;
  statement: string;
  status: string;
  verdict_status?: VerdictStatus;
  created_at: string;
};

export type HypothesesResponse = {
  hypotheses: SavedHypothesis[];
};

export type SavedHypothesisDetail = {
  hypothesis: SavedHypothesis & Partial<HypothesisSpec>;
  runs: RunResult[];
};

export async function fetchResearchFactors(): Promise<AlphaFactorsResponse> {
  const { data } = await api.get<AlphaFactorsResponse>("/alpha-zoo/factors");
  return data;
}

export async function runResearchAutopilot(payload: HypothesisSpec): Promise<RunResult> {
  const { data } = await api.post<RunResult>("/research-autopilot/run", payload);
  return data;
}

export async function saveHypothesis(payload: HypothesisSpec): Promise<SavedHypothesis> {
  const { data } = await api.post<SavedHypothesis>("/research-autopilot/hypotheses", payload);
  return data;
}

export async function listHypotheses(): Promise<HypothesesResponse> {
  const { data } = await api.get<HypothesesResponse>("/research-autopilot/hypotheses");
  return data;
}

export async function fetchHypothesis(id: string): Promise<SavedHypothesisDetail> {
  const { data } = await api.get<SavedHypothesisDetail>(`/research-autopilot/hypotheses/${encodeURIComponent(id)}`);
  return data;
}

export async function runSavedHypothesis(id: string): Promise<RunResult> {
  const { data } = await api.post<RunResult>(`/research-autopilot/hypotheses/${encodeURIComponent(id)}/run`);
  return data;
}
