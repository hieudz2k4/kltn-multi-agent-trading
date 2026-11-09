import { api } from "./base";

export type RobustnessRequest = {
  num_trials?: number;
  bootstrap_paths?: number;
  block_size?: number;
  benchmark_sharpe?: number;
  periods_per_year?: number;
  seed?: number;
};

export type BootstrapMetric = {
  mean: number | null;
  ci_low: number | null;
  ci_high: number | null;
  p_positive: number | null;
};

export type RobustnessVerdict = "robust" | "fragile" | "overfit" | "insufficient";

export type RobustnessReport = {
  run_id: string;
  n_periods: number | null;
  annual_sharpe: number | null;
  skew: number | null;
  kurtosis: number | null;
  psr: number | null;
  dsr: number | null;
  min_track_record_length: number | null;
  bootstrap: {
    method: string | null;
    paths: number | null;
    sharpe: BootstrapMetric;
    cagr: BootstrapMetric;
    max_drawdown: BootstrapMetric;
    sortino: BootstrapMetric;
  } | null;
  stability: {
    rolling_window: number | null;
    pct_windows_positive_sharpe: number | null;
    sharpe_stability: number | null;
  } | null;
  verdict: RobustnessVerdict;
  verdict_reasons: string[];
};

export async function runRobustnessAnalysis(runId: string, body: RobustnessRequest = {}): Promise<RobustnessReport> {
  const { data } = await api.post<RobustnessReport>(`/model-lab/runs/${encodeURIComponent(runId)}/robustness`, body);
  return data;
}
