import { api } from "./base";

export type BiasSeverity = "high" | "moderate" | "low" | string;

export type ShadowBias = {
  score: number | null;
  severity: BiasSeverity;
  detail: string;
  evidence?: string[] | string | null;
};

export type ShadowGroupRow = Record<string, string | number | null | undefined>;

export type ShadowRule = {
  id: string;
  type: string;
  description: string;
  rationale: string;
  impact_hint: string;
};

export type ShadowAccountLeg = {
  trades: number | null;
  pnl: number | null;
  win_rate: number | null;
  expectancy: number | null;
};

export type ShadowViolation = Record<string, string | number | null | undefined>;

export type ShadowAccountReport = {
  summary: Record<string, unknown>;
  profile: {
    win_rate: number | null;
    profit_factor: number | null;
    expectancy: number | null;
    avg_holding_winners: number | null;
    avg_holding_losers: number | null;
    biases: Record<string, ShadowBias>;
    by_setup: ShadowGroupRow[];
    by_strategy: ShadowGroupRow[];
    holding_bucket: ShadowGroupRow[];
  };
  rules: ShadowRule[];
  shadow: {
    actual: ShadowAccountLeg;
    shadow: ShadowAccountLeg;
    improvement_abs: number | null;
    improvement_pct: number | null;
    money_left_on_table: number | null;
    violations: ShadowViolation[];
    counts: Record<string, number | string | null | undefined>;
  };
  meta: {
    closed_trades: number | null;
    generated_at: string | null;
  };
  insufficient_data?: boolean;
  message?: string;
};

export async function fetchShadowAccountReport(): Promise<ShadowAccountReport> {
  const { data } = await api.get<ShadowAccountReport>("/shadow-account/report");
  return data;
}
