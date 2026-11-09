import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { extractApiErrorMessage } from "../api/base";
import { fetchShadowAccountReport, type ShadowAccountLeg, type ShadowAccountReport, type ShadowGroupRow, type ShadowViolation } from "../api/shadowAccount";
import { TerminalBadge } from "../components/terminal/TerminalBadge";
import { TerminalPanel } from "../components/terminal/TerminalPanel";

function formatMoney(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function formatNum(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "--";
  return value.toFixed(digits);
}

function formatPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "--";
  const normalized = Math.abs(value) > 1 ? value : value * 100;
  return `${normalized >= 0 ? "+" : ""}${normalized.toFixed(1)}%`;
}

function severityVariant(severity: string | undefined) {
  const normalized = String(severity || "").toLowerCase();
  if (normalized === "high") return "danger";
  if (normalized === "moderate") return "warn";
  if (normalized === "low") return "success";
  return "neutral";
}

function valueFrom(row: ShadowGroupRow, keys: string[]): string | number | null | undefined {
  for (const key of keys) {
    if (row[key] != null) return row[key];
  }
  return undefined;
}

function rowLabel(row: ShadowGroupRow, fallback: string): string {
  return String(valueFrom(row, ["setup", "strategy", "bucket", "holding_bucket", "name", "label"]) ?? fallback);
}

function rowNumber(row: ShadowGroupRow, keys: string[]): number | null {
  const value = valueFrom(row, keys);
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function ComparisonCard({ title, data }: { title: string; data: ShadowAccountLeg }) {
  return (
    <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-3">
      <div className="text-[10px] uppercase tracking-[0.18em] text-terminal-muted">{title}</div>
      <div className={`mt-2 text-2xl font-semibold tabular-nums ${(data.pnl ?? 0) >= 0 ? "text-terminal-pos" : "text-terminal-neg"}`}>
        {formatMoney(data.pnl)}
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-terminal-muted">
        <div>
          <div>Trades</div>
          <div className="text-terminal-text">{data.trades ?? "--"}</div>
        </div>
        <div>
          <div>Win Rate</div>
          <div className="text-terminal-text">{formatPct(data.win_rate)}</div>
        </div>
        <div>
          <div>Expectancy</div>
          <div className="text-terminal-text">{formatMoney(data.expectancy)}</div>
        </div>
      </div>
    </div>
  );
}

function GroupTable({ title, rows, label }: { title: string; rows: ShadowGroupRow[]; label: string }) {
  return (
    <TerminalPanel title={title} subtitle="Expectancy breakdown">
      <div className="overflow-auto">
        <table className="min-w-full text-[11px]">
          <thead>
            <tr className="border-b border-terminal-border/50 text-terminal-muted">
              <th className="px-2 py-1 text-left">{label}</th>
              <th className="px-2 py-1 text-right">Trades</th>
              <th className="px-2 py-1 text-right">Win Rate</th>
              <th className="px-2 py-1 text-right">Expectancy</th>
              <th className="px-2 py-1 text-right">PnL</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const expectancy = rowNumber(row, ["expectancy", "avg_expectancy"]);
              const pnl = rowNumber(row, ["pnl", "total_pnl", "net_pnl"]);
              return (
                <tr key={`${rowLabel(row, title)}-${index}`} className="border-b border-terminal-border/30">
                  <td className="px-2 py-1 text-terminal-text">{rowLabel(row, `Bucket ${index + 1}`)}</td>
                  <td className="px-2 py-1 text-right tabular-nums">{rowNumber(row, ["trades", "count", "n"]) ?? "--"}</td>
                  <td className="px-2 py-1 text-right tabular-nums">{formatPct(rowNumber(row, ["win_rate"]))}</td>
                  <td className={`px-2 py-1 text-right tabular-nums ${(expectancy ?? 0) >= 0 ? "text-terminal-pos" : "text-terminal-neg"}`}>{formatMoney(expectancy)}</td>
                  <td className={`px-2 py-1 text-right tabular-nums ${(pnl ?? 0) >= 0 ? "text-terminal-pos" : "text-terminal-neg"}`}>{formatMoney(pnl)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!rows.length ? <div className="p-3 text-xs text-terminal-muted">No rows returned yet.</div> : null}
      </div>
    </TerminalPanel>
  );
}

function violationValue(row: ShadowViolation, keys: string[]): string {
  const value = valueFrom(row, keys);
  return value == null || value === "" ? "--" : String(value);
}

function ShadowAccountContent({ report }: { report: ShadowAccountReport }) {
  const biases = useMemo(() => Object.entries(report.profile?.biases ?? {}), [report.profile?.biases]);
  const generatedAt = report.meta?.generated_at ? new Date(report.meta.generated_at).toLocaleString() : "--";

  return (
    <div className="space-y-4">
      <TerminalPanel title="Shadow Account" subtitle={`${report.meta?.closed_trades ?? "--"} closed trades / generated ${generatedAt}`}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-3">
            <div className="text-[10px] uppercase tracking-[0.18em] text-terminal-muted">Win Rate</div>
            <div className="mt-2 text-xl font-semibold text-terminal-text">{formatPct(report.profile?.win_rate)}</div>
          </div>
          <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-3">
            <div className="text-[10px] uppercase tracking-[0.18em] text-terminal-muted">Profit Factor</div>
            <div className="mt-2 text-xl font-semibold text-terminal-accent">{formatNum(report.profile?.profit_factor)}</div>
          </div>
          <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-3">
            <div className="text-[10px] uppercase tracking-[0.18em] text-terminal-muted">Expectancy</div>
            <div className={`mt-2 text-xl font-semibold ${(report.profile?.expectancy ?? 0) >= 0 ? "text-terminal-pos" : "text-terminal-neg"}`}>{formatMoney(report.profile?.expectancy)}</div>
          </div>
          <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-3">
            <div className="text-[10px] uppercase tracking-[0.18em] text-terminal-muted">Hold Winners / Losers</div>
            <div className="mt-2 text-xl font-semibold text-terminal-text">
              {formatNum(report.profile?.avg_holding_winners, 1)}d / {formatNum(report.profile?.avg_holding_losers, 1)}d
            </div>
          </div>
        </div>
      </TerminalPanel>

      <TerminalPanel title="Behavioral Biases" subtitle="Pattern scores from closed-trade journal data">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {biases.map(([name, bias]) => (
            <div key={name} className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-semibold text-terminal-text">{name.replace(/_/g, " ")}</div>
                  <div className="mt-1 text-[11px] text-terminal-muted">Score {formatNum(bias.score)}</div>
                </div>
                <TerminalBadge variant={severityVariant(bias.severity)}>{bias.severity || "unknown"}</TerminalBadge>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-terminal-muted">{bias.detail || "No detail returned."}</p>
              {bias.evidence ? <div className="mt-2 text-[11px] text-terminal-text">{Array.isArray(bias.evidence) ? bias.evidence.join("; ") : bias.evidence}</div> : null}
            </div>
          ))}
          {!biases.length ? <div className="rounded-sm border border-dashed border-terminal-border p-4 text-xs text-terminal-muted">No behavioral bias scores returned.</div> : null}
        </div>
      </TerminalPanel>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <TerminalPanel title="Extracted Rules" subtitle="Rules inferred from repeated journal outcomes">
          <div className="space-y-2">
            {report.rules.map((rule) => (
              <div key={rule.id} className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <TerminalBadge variant="info">{rule.type}</TerminalBadge>
                  <div className="font-semibold text-terminal-text">{rule.description}</div>
                </div>
                <div className="mt-2 text-xs leading-relaxed text-terminal-muted">{rule.rationale}</div>
                {rule.impact_hint ? <div className="mt-2 text-[11px] text-terminal-accent">{rule.impact_hint}</div> : null}
              </div>
            ))}
            {!report.rules.length ? <div className="rounded-sm border border-dashed border-terminal-border p-4 text-xs text-terminal-muted">No rules extracted yet.</div> : null}
          </div>
        </TerminalPanel>

        <TerminalPanel title="Leave On The Table" subtitle="Actual journal vs rule-respecting shadow account">
          <div className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <ComparisonCard title="Actual" data={report.shadow.actual} />
              <ComparisonCard title="Shadow" data={report.shadow.shadow} />
            </div>
            <div className="grid gap-2 text-xs md:grid-cols-3">
              <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-2">
                <div className="text-terminal-muted">Improvement</div>
                <div className="mt-1 text-lg font-semibold text-terminal-accent">{formatMoney(report.shadow.improvement_abs)}</div>
              </div>
              <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-2">
                <div className="text-terminal-muted">Improvement %</div>
                <div className="mt-1 text-lg font-semibold text-terminal-accent">{formatPct(report.shadow.improvement_pct)}</div>
              </div>
              <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-2">
                <div className="text-terminal-muted">Money Left</div>
                <div className="mt-1 text-lg font-semibold text-terminal-warn">{formatMoney(report.shadow.money_left_on_table)}</div>
              </div>
            </div>
            <div className="overflow-auto">
              <table className="min-w-full text-[11px]">
                <thead>
                  <tr className="border-b border-terminal-border/50 text-terminal-muted">
                    <th className="px-2 py-1 text-left">Rule</th>
                    <th className="px-2 py-1 text-left">Symbol</th>
                    <th className="px-2 py-1 text-right">PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {report.shadow.violations.slice(0, 12).map((row, index) => {
                    const pnl = rowNumber(row, ["pnl", "actual_pnl", "trade_pnl"]);
                    return (
                      <tr key={`${violationValue(row, ["rule", "rule_id", "description"])}-${index}`} className="border-b border-terminal-border/30">
                        <td className="px-2 py-1 text-terminal-text">{violationValue(row, ["rule", "rule_id", "description"])}</td>
                        <td className="px-2 py-1 text-terminal-muted">{violationValue(row, ["symbol", "ticker"])}</td>
                        <td className={`px-2 py-1 text-right tabular-nums ${(pnl ?? 0) >= 0 ? "text-terminal-pos" : "text-terminal-neg"}`}>{formatMoney(pnl)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {!report.shadow.violations.length ? <div className="p-3 text-xs text-terminal-muted">No rule violations returned.</div> : null}
            </div>
          </div>
        </TerminalPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <GroupTable title="By Setup" label="Setup" rows={report.profile?.by_setup ?? []} />
        <GroupTable title="Holding Bucket" label="Bucket" rows={report.profile?.holding_bucket ?? []} />
      </div>
    </div>
  );
}

export function ShadowAccountPage() {
  const reportQuery = useQuery({
    queryKey: ["shadow-account", "report"],
    queryFn: fetchShadowAccountReport,
  });

  const error = reportQuery.error ? extractApiErrorMessage(reportQuery.error, "Failed to load shadow account report.") : "";
  const report = reportQuery.data;

  return (
    <div className="space-y-4 p-4" data-testid="shadow-account-page">
      {reportQuery.isLoading ? (
        <TerminalPanel title="Shadow Account" subtitle="Loading behavioral diagnostics">
          <div className="space-y-2" aria-live="polite">
            <div className="h-8 rounded-sm border border-terminal-border bg-terminal-bg/60" />
            <div className="h-24 rounded-sm border border-terminal-border bg-terminal-bg/60" />
            <div className="h-24 rounded-sm border border-terminal-border bg-terminal-bg/60" />
          </div>
        </TerminalPanel>
      ) : null}

      {error ? (
        <TerminalPanel title="Shadow Account" subtitle="Report unavailable">
          <div className="rounded-sm border border-terminal-neg/50 bg-terminal-neg/10 p-3 text-xs text-terminal-neg">{error}</div>
        </TerminalPanel>
      ) : null}

      {report?.insufficient_data ? (
        <TerminalPanel title="Shadow Account" subtitle="More closed trades needed">
          <div className="rounded-sm border border-dashed border-terminal-border p-6 text-sm leading-relaxed text-terminal-muted">
            <div className="mb-2 text-terminal-text">{report.message || "There is not enough closed-trade history to build a shadow account yet."}</div>
            Log more closed trades in the journal, including setup, strategy, exit, and notes, then return here for bias scoring and counterfactual rules.
          </div>
        </TerminalPanel>
      ) : null}

      {report && !report.insufficient_data ? <ShadowAccountContent report={report} /> : null}
    </div>
  );
}
