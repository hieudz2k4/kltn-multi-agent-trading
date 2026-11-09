import { useMutation } from "@tanstack/react-query";

import { runRobustnessAnalysis, type RobustnessReport, type RobustnessVerdict } from "../../api/robustness";
import { extractApiErrorMessage } from "../../api/base";
import { TerminalBadge } from "../terminal/TerminalBadge";
import { TerminalButton } from "../terminal/TerminalButton";
import { TerminalPanel } from "../terminal/TerminalPanel";

type Props = {
  runId: string;
};

function formatNum(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "--";
  return value.toFixed(digits);
}

function formatPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "--";
  return `${(value * 100).toFixed(1)}%`;
}

function verdictVariant(verdict: RobustnessVerdict | undefined) {
  if (verdict === "robust") return "success";
  if (verdict === "fragile") return "warn";
  if (verdict === "overfit") return "danger";
  return "neutral";
}

function metricTone(value: number | null | undefined, threshold = 0.95): string {
  if (value == null || !Number.isFinite(value)) return "text-terminal-muted";
  return value >= threshold ? "text-terminal-pos" : value >= 0.75 ? "text-terminal-warn" : "text-terminal-neg";
}

function MetricCard({ label, value, tone = "text-terminal-accent" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-2">
      <div className="text-[10px] uppercase tracking-[0.18em] text-terminal-muted">{label}</div>
      <div className={`mt-1 text-lg font-semibold tabular-nums ${tone}`}>{value}</div>
    </div>
  );
}

function BootstrapSharpe({ report }: { report: RobustnessReport }) {
  const sharpe = report.bootstrap?.sharpe;
  if (!sharpe) {
    return <div className="rounded-sm border border-dashed border-terminal-border p-3 text-xs text-terminal-muted">Bootstrap Sharpe interval is unavailable for this run.</div>;
  }
  return (
    <div className="space-y-2 rounded-sm border border-terminal-border bg-terminal-bg/50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="ot-type-panel-title text-terminal-text">Bootstrap Sharpe CI</div>
          <div className="text-[11px] text-terminal-muted">
            {report.bootstrap?.method || "bootstrap"} / {report.bootstrap?.paths ?? "--"} paths
          </div>
        </div>
        <TerminalBadge variant="info">p_positive {formatPct(sharpe.p_positive)}</TerminalBadge>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <div className="text-terminal-muted">Low</div>
          <div className="tabular-nums text-terminal-neg">{formatNum(sharpe.ci_low)}</div>
        </div>
        <div>
          <div className="text-terminal-muted">Mean</div>
          <div className="tabular-nums text-terminal-accent">{formatNum(sharpe.mean)}</div>
        </div>
        <div>
          <div className="text-terminal-muted">High</div>
          <div className="tabular-nums text-terminal-pos">{formatNum(sharpe.ci_high)}</div>
        </div>
      </div>
    </div>
  );
}

export function RobustnessPanel({ runId }: Props) {
  const mutation = useMutation({
    mutationFn: () => runRobustnessAnalysis(runId),
  });

  const report = mutation.data;
  const error = mutation.error ? extractApiErrorMessage(mutation.error, "Failed to run robustness analysis.") : "";

  return (
    <TerminalPanel
      title="Robustness Scorecard"
      subtitle="PSR, DSR, bootstrap confidence intervals, and verdict"
      actions={
        <TerminalButton type="button" size="sm" variant="accent" loading={mutation.isPending} disabled={!runId} onClick={() => mutation.mutate()}>
          Run robustness analysis
        </TerminalButton>
      }
    >
      <div className="space-y-3" aria-live="polite">
        {!report && !mutation.isPending && !error ? (
          <div className="rounded-sm border border-dashed border-terminal-border p-4 text-xs leading-relaxed text-terminal-muted">
            Run the scorecard to test whether the backtest survives non-normal returns, selection effects, and bootstrap path uncertainty.
          </div>
        ) : null}
        {mutation.isPending ? <div className="text-xs text-terminal-muted">Running robustness analysis...</div> : null}
        {error ? <div className="rounded-sm border border-terminal-neg/50 bg-terminal-neg/10 p-3 text-xs text-terminal-neg">{error}</div> : null}
        {report ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs text-terminal-muted">
                {report.n_periods ?? "--"} periods / MTRL {formatNum(report.min_track_record_length, 1)}
              </div>
              <TerminalBadge variant={verdictVariant(report.verdict)} size="md" dot>
                {report.verdict}
              </TerminalBadge>
            </div>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <MetricCard label="PSR" value={formatPct(report.psr)} tone={metricTone(report.psr)} />
              <MetricCard label="DSR" value={formatPct(report.dsr)} tone={metricTone(report.dsr)} />
              <MetricCard label="Annual Sharpe" value={formatNum(report.annual_sharpe)} />
              <MetricCard label="Sharpe Stability" value={formatNum(report.stability?.sharpe_stability)} />
            </div>
            <BootstrapSharpe report={report} />
            <div className="rounded-sm border border-terminal-border bg-terminal-bg/50 p-3">
              <div className="mb-2 ot-type-panel-title text-terminal-text">Verdict reasons</div>
              {report.verdict_reasons.length ? (
                <ul className="space-y-1 text-xs text-terminal-muted">
                  {report.verdict_reasons.map((reason) => (
                    <li key={reason} className="leading-relaxed">
                      {reason}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-xs text-terminal-muted">No specific reasons returned.</div>
              )}
            </div>
          </>
        ) : null}
      </div>
    </TerminalPanel>
  );
}
