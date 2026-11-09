import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookmarkPlus, CheckCircle2, CircleDot, Play, RefreshCw, XCircle } from "lucide-react";

import { extractApiErrorMessage } from "../api/base";
import {
  fetchHypothesis,
  fetchResearchFactors,
  listHypotheses,
  runResearchAutopilot,
  runSavedHypothesis,
  saveHypothesis,
  type AlphaFactorOption,
  type CriteriaResult,
  type CurvePoint,
  type HypothesisSpec,
  type RegimeAttribution,
  type RunResult,
  type SavedHypothesisDetail,
  type SignalDirection,
  type SignalKind,
  type VerdictStatus,
} from "../api/researchAutopilot";
import { TerminalBadge } from "../components/terminal/TerminalBadge";
import { TerminalButton } from "../components/terminal/TerminalButton";
import { TerminalInput } from "../components/terminal/TerminalInput";
import { TerminalPanel } from "../components/terminal/TerminalPanel";

const DEFAULT_UNIVERSE = "AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, JPM";
const RANGE_OPTIONS = ["1y", "2y", "3y"] as const;

type CriterionKey = "min_sharpe" | "min_psr" | "max_drawdown" | "min_hit_rate";

const criterionLabels: Record<CriterionKey, string> = {
  min_sharpe: "Min Sharpe",
  min_psr: "Min PSR",
  max_drawdown: "Max Drawdown",
  min_hit_rate: "Min Hit-rate",
};

function parseUniverse(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
}

function finiteOrUndefined(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatNum(value: unknown, digits = 2): string {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "--";
}

function formatPct(value: unknown, digits = 1): string {
  const n = Number(value);
  return Number.isFinite(n) ? `${(n * 100).toFixed(digits)}%` : "--";
}

function compactDate(value: string): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "2-digit" });
}

function verdictVariant(status: VerdictStatus | string | undefined): "success" | "danger" | "warn" | "neutral" {
  if (status === "accepted") return "success";
  if (status === "rejected") return "danger";
  if (status === "inconclusive") return "warn";
  return "neutral";
}

function verdictClass(status: VerdictStatus): string {
  if (status === "accepted") return "border-terminal-pos bg-terminal-pos/10 text-terminal-pos";
  if (status === "rejected") return "border-terminal-neg bg-terminal-neg/10 text-terminal-neg";
  return "border-terminal-warn bg-terminal-warn/10 text-terminal-warn";
}

function formatCriteriaValue(name: string, value: number | string): string {
  if (typeof value === "string") return value;
  const lower = name.toLowerCase();
  if (lower.includes("drawdown") || lower.includes("cagr") || lower.includes("psr") || lower.includes("hit")) {
    return formatPct(value);
  }
  return formatNum(value, 3);
}

function MetricTile({ label, value, tone = "text-terminal-text" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-sm border border-terminal-border bg-terminal-bg/60 p-3">
      <div className="text-[10px] uppercase tracking-[0.14em] text-terminal-muted">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${tone}`}>{value}</div>
    </div>
  );
}

function EmptyState({ children }: { children: string }) {
  return (
    <div className="rounded-sm border border-dashed border-terminal-border/80 p-5 text-center text-xs leading-relaxed text-terminal-muted">
      {children}
    </div>
  );
}

function CriteriaTable({ rows }: { rows: CriteriaResult[] }) {
  if (!rows.length) return <EmptyState>Run verdict criteria will appear after the first completed loop.</EmptyState>;
  return (
    <div className="overflow-auto">
      <table className="w-full min-w-[540px] text-[11px]">
        <thead>
          <tr className="border-b border-terminal-border/70 text-terminal-muted">
            {["Criterion", "Target", "Actual", "Result"].map((header) => (
              <th key={header} className="px-2 py-2 text-left font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name} className="border-b border-terminal-border/30">
              <td className="px-2 py-2 text-terminal-text">{row.name}</td>
              <td className="px-2 py-2 tabular-nums text-terminal-muted">{formatCriteriaValue(row.name, row.target)}</td>
              <td className="px-2 py-2 tabular-nums text-terminal-text">{formatCriteriaValue(row.name, row.actual)}</td>
              <td className="px-2 py-2">
                <TerminalBadge variant={row.pass ? "success" : "danger"} dot>
                  {row.pass ? "pass" : "fail"}
                </TerminalBadge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LineChart({ equity, benchmark }: { equity: CurvePoint[]; benchmark: CurvePoint[] }) {
  const series = useMemo(() => {
    const points = [...equity, ...benchmark].map((point) => Number(point.value)).filter(Number.isFinite);
    const min = Math.min(...points);
    const max = Math.max(...points);
    const span = max - min || 1;
    const makePath = (items: CurvePoint[]) =>
      items
        .map((point, index) => {
          const x = items.length <= 1 ? 0 : (index / (items.length - 1)) * 100;
          const y = 92 - ((Number(point.value) - min) / span) * 84;
          return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
        })
        .join(" ");
    return {
      equityPath: makePath(equity),
      benchmarkPath: makePath(benchmark),
      firstDate: equity[0]?.date || benchmark[0]?.date,
      lastDate: equity[equity.length - 1]?.date || benchmark[benchmark.length - 1]?.date,
    };
  }, [benchmark, equity]);

  if (!equity.length && !benchmark.length) return <EmptyState>Equity and benchmark curves are not available for this run.</EmptyState>;

  return (
    <div className="rounded-sm border border-terminal-border bg-terminal-bg/50 p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-terminal-muted">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1"><span className="h-1.5 w-4 rounded-sm bg-terminal-accent" />Equity</span>
          <span className="inline-flex items-center gap-1"><span className="h-1.5 w-4 rounded-sm bg-terminal-muted" />Benchmark</span>
        </div>
        <span>{compactDate(series.firstDate)} to {compactDate(series.lastDate)}</span>
      </div>
      <svg viewBox="0 0 100 100" role="img" aria-label="Equity curve compared with benchmark" className="h-56 w-full overflow-visible">
        <defs>
          <linearGradient id="research-autopilot-equity-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--ot-color-accent-primary)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="var(--ot-color-accent-primary)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[8, 29, 50, 71, 92].map((y) => (
          <line key={y} x1="0" x2="100" y1={y} y2={y} stroke="var(--ot-color-border-default)" strokeOpacity="0.45" strokeWidth="0.25" />
        ))}
        {series.benchmarkPath ? (
          <path d={series.benchmarkPath} fill="none" stroke="var(--ot-color-text-muted)" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
        ) : null}
        {series.equityPath ? (
          <>
            <path d={`${series.equityPath} L 100 96 L 0 96 Z`} fill="url(#research-autopilot-equity-fill)" opacity="0.9" />
            <path d={series.equityPath} fill="none" stroke="var(--ot-color-accent-primary)" strokeWidth="1.8" vectorEffect="non-scaling-stroke" />
          </>
        ) : null}
      </svg>
    </div>
  );
}

function RegimeTable({ rows }: { rows: RegimeAttribution[] }) {
  if (!rows.length) return <EmptyState>Regime attribution was not returned for this run.</EmptyState>;
  return (
    <div className="overflow-auto">
      <table className="w-full min-w-[620px] text-[11px]">
        <thead>
          <tr className="border-b border-terminal-border/70 text-terminal-muted">
            {["Regime", "Days", "Avg Daily", "Total Return", "Contribution"].map((header) => (
              <th key={header} className="px-2 py-2 text-left font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.regime} className="border-b border-terminal-border/30">
              <td className="px-2 py-2 text-terminal-text">{row.regime}</td>
              <td className="px-2 py-2 tabular-nums text-terminal-muted">{row.days}</td>
              <td className="px-2 py-2 tabular-nums text-terminal-text">{formatPct(row.avg_daily_return, 2)}</td>
              <td className="px-2 py-2 tabular-nums text-terminal-text">{formatPct(row.total_return)}</td>
              <td className="px-2 py-2 tabular-nums text-terminal-accent">{formatPct(row.contribution)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PeriodList({ title, rows, tone }: { title: string; rows: Array<{ date: string; return: number }>; tone: string }) {
  return (
    <div className="rounded-sm border border-terminal-border bg-terminal-bg/50 p-3">
      <div className="mb-2 text-[11px] font-semibold text-terminal-text">{title}</div>
      {rows.length ? (
        <div className="space-y-1">
          {rows.slice(0, 5).map((row) => (
            <div key={`${title}-${row.date}`} className="flex items-center justify-between gap-3 text-[11px]">
              <span className="text-terminal-muted">{row.date}</span>
              <span className={`tabular-nums ${tone}`}>{formatPct(row.return, 2)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-[11px] text-terminal-muted">No periods returned.</div>
      )}
    </div>
  );
}

function applyLoadedHypothesis(detail: SavedHypothesisDetail, setters: {
  setStatement: (value: string) => void;
  setUniverseText: (value: string) => void;
  setBenchmark: (value: string) => void;
  setSignalKind: (value: SignalKind) => void;
  setDirection: (value: SignalDirection) => void;
  setSelectedFactorId: (value: string) => void;
  setLookbackDays: (value: number) => void;
  setRange: (value: string) => void;
  setRebalanceDays: (value: number) => void;
  setTopQuantile: (value: number) => void;
  setCriteria: (value: Record<CriterionKey, string>) => void;
}) {
  const hypothesis = detail.hypothesis;
  setters.setStatement(hypothesis.statement || "");
  if (hypothesis.universe?.length) setters.setUniverseText(hypothesis.universe.join(", "));
  if (hypothesis.benchmark) setters.setBenchmark(hypothesis.benchmark);
  if (hypothesis.signal?.kind) setters.setSignalKind(hypothesis.signal.kind);
  if (hypothesis.signal?.direction) setters.setDirection(hypothesis.signal.direction);
  if (hypothesis.signal?.factor_id) setters.setSelectedFactorId(hypothesis.signal.factor_id);
  if (hypothesis.signal?.lookback_days) setters.setLookbackDays(hypothesis.signal.lookback_days);
  if (hypothesis.range) setters.setRange(hypothesis.range);
  if (hypothesis.rebalance_days) setters.setRebalanceDays(hypothesis.rebalance_days);
  if (hypothesis.top_quantile) setters.setTopQuantile(hypothesis.top_quantile);
  setters.setCriteria({
    min_sharpe: hypothesis.acceptance?.min_sharpe?.toString() ?? "",
    min_psr: hypothesis.acceptance?.min_psr?.toString() ?? "",
    max_drawdown: hypothesis.acceptance?.max_drawdown?.toString() ?? "",
    min_hit_rate: hypothesis.acceptance?.min_hit_rate?.toString() ?? "",
  });
}

export function ResearchAutopilotPage() {
  const queryClient = useQueryClient();
  const [statement, setStatement] = useState("Large-cap AI infrastructure leaders should retain positive risk-adjusted momentum versus SPY.");
  const [universeText, setUniverseText] = useState(DEFAULT_UNIVERSE);
  const [benchmark, setBenchmark] = useState("SPY");
  const [signalKind, setSignalKind] = useState<SignalKind>("alpha_factor");
  const [selectedFactorId, setSelectedFactorId] = useState("");
  const [lookbackDays, setLookbackDays] = useState(63);
  const [direction, setDirection] = useState<SignalDirection>("long_only");
  const [range, setRange] = useState("2y");
  const [rebalanceDays, setRebalanceDays] = useState(21);
  const [topQuantile, setTopQuantile] = useState(0.25);
  const [criteria, setCriteria] = useState<Record<CriterionKey, string>>({
    min_sharpe: "0.8",
    min_psr: "0.75",
    max_drawdown: "0.25",
    min_hit_rate: "",
  });
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string | null>(null);

  const factorsQuery = useQuery({
    queryKey: ["research-autopilot", "factors"],
    queryFn: fetchResearchFactors,
  });
  const hypothesesQuery = useQuery({
    queryKey: ["research-autopilot", "hypotheses"],
    queryFn: listHypotheses,
  });

  const factors = factorsQuery.data?.factors ?? [];
  const groupedFactors = useMemo(() => {
    const groups = new Map<string, AlphaFactorOption[]>();
    for (const factor of factors) {
      groups.set(factor.zoo || "Other", [...(groups.get(factor.zoo || "Other") ?? []), factor]);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [factors]);

  const activeFactorId = selectedFactorId || factors[0]?.id || "";
  const selectedFactor = factors.find((factor) => factor.id === activeFactorId);
  const universe = useMemo(() => parseUniverse(universeText), [universeText]);

  const buildSpec = (): HypothesisSpec => ({
    statement: statement.trim(),
    universe,
    benchmark: benchmark.trim() || undefined,
    signal:
      signalKind === "alpha_factor"
        ? { kind: "alpha_factor", factor_id: activeFactorId || undefined, direction }
        : { kind: "momentum", lookback_days: lookbackDays, direction },
    acceptance: {
      min_sharpe: finiteOrUndefined(criteria.min_sharpe),
      min_psr: finiteOrUndefined(criteria.min_psr),
      max_drawdown: finiteOrUndefined(criteria.max_drawdown),
      min_hit_rate: finiteOrUndefined(criteria.min_hit_rate),
    },
    range,
    rebalance_days: rebalanceDays,
    top_quantile: topQuantile,
    long_short: direction === "long_short",
  });

  const runMutation = useMutation({
    mutationFn: () => runResearchAutopilot(buildSpec()),
    onSuccess: setRunResult,
  });
  const saveMutation = useMutation({
    mutationFn: () => saveHypothesis(buildSpec()),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["research-autopilot", "hypotheses"] });
    },
  });
  const loadMutation = useMutation({
    mutationFn: fetchHypothesis,
    onSuccess: (detail) => {
      applyLoadedHypothesis(detail, {
        setStatement,
        setUniverseText,
        setBenchmark,
        setSignalKind,
        setDirection,
        setSelectedFactorId,
        setLookbackDays,
        setRange,
        setRebalanceDays,
        setTopQuantile,
        setCriteria,
      });
      setRunResult(detail.runs[0] ?? null);
    },
  });
  const runSavedMutation = useMutation({
    mutationFn: runSavedHypothesis,
    onSuccess: async (result) => {
      setRunResult(result);
      await queryClient.invalidateQueries({ queryKey: ["research-autopilot", "hypotheses"] });
    },
  });

  const pageError = factorsQuery.error || hypothesesQuery.error || runMutation.error || saveMutation.error || loadMutation.error || runSavedMutation.error;
  const errorMessage = pageError ? extractApiErrorMessage(pageError, "Research Autopilot request failed.") : "";
  const canRun = statement.trim().length > 0 && universe.length > 0 && (signalKind === "momentum" || Boolean(activeFactorId));
  const result = runResult;
  const missing = result?.coverage.missing ?? [];
  const metrics = result?.backtest.metrics;
  const permutation = result?.attribution.permutation;
  const exposure = result?.attribution.factor_exposure;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (canRun) runMutation.mutate();
  };

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top_left,rgba(255,107,0,0.08),transparent_34rem)] p-3 md:p-5">
      <main className="mx-auto flex w-full max-w-[1680px] flex-col gap-4">
        <section className="rounded-md border border-terminal-border/70 bg-terminal-panel/95 p-4 md:p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <div className="mb-2 flex flex-wrap gap-2">
                <TerminalBadge variant="accent">Research Autopilot</TerminalBadge>
                <TerminalBadge variant="neutral">{factors.length || "--"} factors</TerminalBadge>
                {result ? <TerminalBadge variant="info">run {result.run_id}</TerminalBadge> : null}
              </div>
              <h1 className="font-sans text-2xl font-semibold tracking-normal text-terminal-text md:text-3xl">
                Define a hypothesis, run the loop, read the verdict.
              </h1>
              <p className="mt-2 max-w-3xl font-sans text-sm leading-6 text-terminal-muted">
                Backtest, attribution, significance, robustness, and acceptance criteria stay attached to the same research question.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs md:min-w-[420px]">
              <MetricTile label="Universe" value={String(universe.length)} />
              <MetricTile label="Range" value={range} />
              <MetricTile label="Saved" value={String(hypothesesQuery.data?.hypotheses.length ?? "--")} />
            </div>
          </div>
        </section>

        {errorMessage ? (
          <div className="rounded-sm border border-terminal-neg/70 bg-terminal-neg/10 px-3 py-2 text-xs text-terminal-neg" role="alert">
            {errorMessage}
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[400px_minmax(0,1fr)]">
          <div className="space-y-4">
            <TerminalPanel title="Builder" subtitle="Signal, universe, and acceptance criteria">
              <form onSubmit={onSubmit} className="space-y-3">
                <label className="block">
                  <span className="mb-1 block text-xs text-terminal-muted">Hypothesis statement</span>
                  <TerminalInput as="textarea" rows={4} value={statement} onChange={(event) => setStatement(event.target.value)} tone="ui" />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs text-terminal-muted">Universe</span>
                  <TerminalInput as="textarea" rows={3} value={universeText} onChange={(event) => setUniverseText(event.target.value)} tone="ui" />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="block">
                    <span className="mb-1 block text-xs text-terminal-muted">Benchmark</span>
                    <TerminalInput value={benchmark} onChange={(event) => setBenchmark(event.target.value.toUpperCase())} tone="ui" />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs text-terminal-muted">Range</span>
                    <TerminalInput as="select" value={range} onChange={(event) => setRange(event.target.value)} tone="ui">
                      {RANGE_OPTIONS.map((item) => <option key={item} value={item}>{item}</option>)}
                    </TerminalInput>
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-2" role="group" aria-label="Signal kind">
                  {(["alpha_factor", "momentum"] as SignalKind[]).map((kind) => (
                    <button
                      key={kind}
                      type="button"
                      className={`rounded-sm border px-3 py-2 text-xs outline-none focus-visible:ring-1 focus-visible:ring-terminal-accent/40 ${
                        signalKind === kind ? "border-terminal-accent bg-terminal-accent/15 text-terminal-accent" : "border-terminal-border text-terminal-muted hover:text-terminal-text"
                      }`}
                      onClick={() => setSignalKind(kind)}
                    >
                      {kind === "alpha_factor" ? "Alpha Factor" : "Momentum"}
                    </button>
                  ))}
                </div>

                {signalKind === "alpha_factor" ? (
                  <label className="block">
                    <span className="mb-1 block text-xs text-terminal-muted">Factor</span>
                    <TerminalInput
                      as="select"
                      value={activeFactorId}
                      onChange={(event) => setSelectedFactorId(event.target.value)}
                      tone="ui"
                      loading={factorsQuery.isLoading}
                      disabled={factorsQuery.isLoading || !factors.length}
                    >
                      {groupedFactors.map(([zoo, options]) => (
                        <optgroup key={zoo} label={zoo}>
                          {options.map((factor) => (
                            <option key={factor.id} value={factor.id}>
                              {factor.name} ({factor.category})
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </TerminalInput>
                    {selectedFactor ? (
                      <span className="mt-1 block text-[11px] leading-relaxed text-terminal-muted">{selectedFactor.description || selectedFactor.id}</span>
                    ) : null}
                  </label>
                ) : (
                  <label className="block">
                    <span className="mb-1 block text-xs text-terminal-muted">Lookback days</span>
                    <TerminalInput type="number" min={5} max={504} value={lookbackDays} onChange={(event) => setLookbackDays(Math.max(5, Number(event.target.value) || 5))} tone="ui" />
                  </label>
                )}

                <div className="grid grid-cols-2 gap-2" role="group" aria-label="Direction">
                  {(["long_only", "long_short"] as SignalDirection[]).map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={`rounded-sm border px-3 py-2 text-xs outline-none focus-visible:ring-1 focus-visible:ring-terminal-accent/40 ${
                        direction === item ? "border-terminal-accent bg-terminal-accent/15 text-terminal-accent" : "border-terminal-border text-terminal-muted hover:text-terminal-text"
                      }`}
                      onClick={() => setDirection(item)}
                    >
                      {item === "long_only" ? "Long only" : "Long/short"}
                    </button>
                  ))}
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <label className="block">
                    <span className="mb-1 block text-xs text-terminal-muted">Rebalance days</span>
                    <TerminalInput type="number" min={1} max={126} value={rebalanceDays} onChange={(event) => setRebalanceDays(Math.max(1, Number(event.target.value) || 1))} tone="ui" />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs text-terminal-muted">Top quantile</span>
                    <TerminalInput type="number" min={0.05} max={1} step={0.05} value={topQuantile} onChange={(event) => setTopQuantile(Math.min(1, Math.max(0.05, Number(event.target.value) || 0.05)))} tone="ui" />
                  </label>
                </div>

                <div>
                  <div className="mb-2 text-xs text-terminal-muted">Acceptance criteria</div>
                  <div className="grid grid-cols-2 gap-2">
                    {(Object.keys(criterionLabels) as CriterionKey[]).map((key) => (
                      <label key={key} className="block">
                        <span className="mb-1 block text-[11px] text-terminal-muted">{criterionLabels[key]}</span>
                        <TerminalInput
                          type="number"
                          step="0.01"
                          value={criteria[key]}
                          onChange={(event) => setCriteria((current) => ({ ...current, [key]: event.target.value }))}
                          placeholder="optional"
                          tone="ui"
                        />
                      </label>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-1">
                  <TerminalButton type="submit" variant="accent" loading={runMutation.isPending} disabled={!canRun} leftIcon={<Play className="h-3.5 w-3.5" />}>
                    Run loop
                  </TerminalButton>
                  <TerminalButton type="button" variant="default" loading={saveMutation.isPending} disabled={!canRun} onClick={() => saveMutation.mutate()} leftIcon={<BookmarkPlus className="h-3.5 w-3.5" />}>
                    Save
                  </TerminalButton>
                </div>
              </form>
            </TerminalPanel>

            <TerminalPanel title="Saved Hypotheses" subtitle="Load prior research questions">
              {hypothesesQuery.isLoading ? <div className="text-xs text-terminal-muted">Loading saved hypotheses...</div> : null}
              {!hypothesesQuery.isLoading && !hypothesesQuery.data?.hypotheses.length ? (
                <EmptyState>Saved hypotheses will appear here after you save a builder spec.</EmptyState>
              ) : null}
              <div className="space-y-2">
                {(hypothesesQuery.data?.hypotheses ?? []).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`w-full rounded-sm border p-3 text-left outline-none transition-colors focus-visible:ring-1 focus-visible:ring-terminal-accent/40 ${
                      selectedHypothesisId === item.id ? "border-terminal-accent bg-terminal-accent/10" : "border-terminal-border bg-terminal-bg/40 hover:border-terminal-accent/70"
                    }`}
                    onClick={() => {
                      setSelectedHypothesisId(item.id);
                      loadMutation.mutate(item.id);
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="line-clamp-2 text-xs font-semibold text-terminal-text">{item.statement}</span>
                      <TerminalBadge variant={verdictVariant(item.verdict_status || item.status)}>{item.verdict_status || item.status}</TerminalBadge>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2 text-[10px] text-terminal-muted">
                      <span>{item.created_at ? new Date(item.created_at).toLocaleDateString() : item.id}</span>
                      <span>{selectedHypothesisId === item.id && loadMutation.isPending ? "loading..." : item.id}</span>
                    </div>
                  </button>
                ))}
              </div>
              {selectedHypothesisId ? (
                <TerminalButton
                  type="button"
                  size="md"
                  variant="accent"
                  className="mt-3 w-full"
                  loading={runSavedMutation.isPending}
                  onClick={() => runSavedMutation.mutate(selectedHypothesisId)}
                  leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
                >
                  Run selected
                </TerminalButton>
              ) : null}
            </TerminalPanel>
          </div>

          <div className="space-y-4">
            {!result && !runMutation.isPending ? (
              <TerminalPanel title="Result" subtitle="Verdict appears after the loop completes">
                <EmptyState>Configure a hypothesis, then run the loop to produce a verdict, backtest, attribution, and robustness scorecard.</EmptyState>
              </TerminalPanel>
            ) : null}
            {runMutation.isPending ? (
              <TerminalPanel title="Running" subtitle="Closed research loop">
                <div className="flex items-center gap-2 text-xs text-terminal-muted">
                  <CircleDot className="h-4 w-4 animate-pulse text-terminal-accent" />
                  Backtest, attribution, robustness, and verdict are being computed.
                </div>
              </TerminalPanel>
            ) : null}

            {result ? (
              <>
                <section className={`rounded-md border p-4 ${verdictClass(result.verdict.status)}`}>
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        {result.verdict.status === "accepted" ? <CheckCircle2 className="h-5 w-5" /> : result.verdict.status === "rejected" ? <XCircle className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
                        <h2 className="font-sans text-xl font-semibold tracking-normal uppercase">{result.verdict.status}</h2>
                      </div>
                      <div className="mt-2 max-w-4xl text-xs leading-relaxed">
                        {result.verdict.reasons.length ? result.verdict.reasons.join(" ") : "No verdict reasons returned."}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] uppercase tracking-[0.14em] opacity-80">Score</div>
                      <div className="text-3xl font-semibold tabular-nums">{formatNum(result.verdict.score, 2)}</div>
                    </div>
                  </div>
                </section>

                <TerminalPanel title="Acceptance Criteria" subtitle="Target versus realized result">
                  <CriteriaTable rows={result.verdict.criteria_results} />
                </TerminalPanel>

                <TerminalPanel title="Backtest" subtitle={`${result.backtest.bars} bars, rebalance every ${result.backtest.rebalance_days} days`}>
                  <div className="space-y-3">
                    {missing.length ? (
                      <div className="rounded-sm border border-terminal-warn/60 bg-terminal-warn/10 px-3 py-2 text-xs text-terminal-warn">
                        Coverage warning: missing {missing.join(", ")}
                      </div>
                    ) : null}
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
                      <MetricTile label="CAGR" value={formatPct(metrics?.cagr)} tone="text-terminal-pos" />
                      <MetricTile label="Sharpe" value={formatNum(metrics?.sharpe)} />
                      <MetricTile label="Sortino" value={formatNum(metrics?.sortino)} />
                      <MetricTile label="Max DD" value={formatPct(metrics?.max_drawdown)} tone="text-terminal-neg" />
                      <MetricTile label="Hit-rate" value={formatPct(metrics?.hit_rate)} />
                      <MetricTile label="Turnover" value={formatPct(metrics?.turnover)} />
                    </div>
                    <LineChart equity={result.backtest.equity_curve} benchmark={result.backtest.benchmark_curve} />
                  </div>
                </TerminalPanel>

                <TerminalPanel title="Attribution" subtitle="Regimes, significance, exposure, and best/worst periods">
                  <div className="space-y-3">
                    <RegimeTable rows={result.attribution.regime} />
                    <div className="grid gap-3 lg:grid-cols-3">
                      <div className="rounded-sm border border-terminal-border bg-terminal-bg/50 p-3">
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <div className="text-[11px] font-semibold text-terminal-text">Permutation</div>
                          <TerminalBadge variant={permutation && permutation.p_value < 0.05 ? "success" : "warn"}>
                            {permutation && permutation.p_value < 0.05 ? "significant" : "not significant"}
                          </TerminalBadge>
                        </div>
                        <div className="space-y-1 text-[11px]">
                          <div className="flex justify-between"><span className="text-terminal-muted">Observed Sharpe</span><span className="tabular-nums text-terminal-text">{formatNum(permutation?.observed_sharpe)}</span></div>
                          <div className="flex justify-between"><span className="text-terminal-muted">p-value</span><span className="tabular-nums text-terminal-text">{formatNum(permutation?.p_value, 4)}</span></div>
                          <div className="flex justify-between"><span className="text-terminal-muted">Trials</span><span className="tabular-nums text-terminal-text">{permutation?.trials ?? "--"}</span></div>
                          <div className="flex justify-between"><span className="text-terminal-muted">Better count</span><span className="tabular-nums text-terminal-text">{permutation?.better_count ?? "--"}</span></div>
                        </div>
                      </div>
                      <div className="rounded-sm border border-terminal-border bg-terminal-bg/50 p-3">
                        <div className="mb-2 text-[11px] font-semibold text-terminal-text">Factor Exposure</div>
                        <div className="space-y-1 text-[11px]">
                          <div className="flex justify-between"><span className="text-terminal-muted">Annual alpha</span><span className="tabular-nums text-terminal-accent">{formatPct(exposure?.alpha_annual)}</span></div>
                          <div className="flex justify-between"><span className="text-terminal-muted">Beta</span><span className="tabular-nums text-terminal-text">{formatNum(exposure?.beta)}</span></div>
                          <div className="flex justify-between"><span className="text-terminal-muted">R squared</span><span className="tabular-nums text-terminal-text">{formatPct(exposure?.r_squared)}</span></div>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
                        <PeriodList title="Top periods" rows={result.attribution.top_periods} tone="text-terminal-pos" />
                        <PeriodList title="Worst periods" rows={result.attribution.worst_periods} tone="text-terminal-neg" />
                      </div>
                    </div>
                  </div>
                </TerminalPanel>

                <TerminalPanel title="Robustness Scorecard" subtitle="Probabilistic and deflated Sharpe checks">
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-xs text-terminal-muted">Annual Sharpe {formatNum(result.robustness.annual_sharpe)}</div>
                      <TerminalBadge variant={result.robustness.verdict === "robust" ? "success" : result.robustness.verdict === "overfit" ? "danger" : "warn"} dot>
                        {result.robustness.verdict || "unknown"}
                      </TerminalBadge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                      <MetricTile label="PSR" value={formatPct(result.robustness.psr)} tone={result.robustness.psr >= 0.75 ? "text-terminal-pos" : "text-terminal-warn"} />
                      <MetricTile label="DSR" value={formatPct(result.robustness.dsr)} tone={result.robustness.dsr >= 0.75 ? "text-terminal-pos" : "text-terminal-warn"} />
                      <MetricTile label="Annual Sharpe" value={formatNum(result.robustness.annual_sharpe)} />
                    </div>
                    <div className="rounded-sm border border-terminal-border bg-terminal-bg/50 p-3">
                      <div className="mb-2 text-[11px] font-semibold text-terminal-text">Verdict reasons</div>
                      {result.robustness.verdict_reasons.length ? (
                        <ul className="space-y-1 text-xs leading-relaxed text-terminal-muted">
                          {result.robustness.verdict_reasons.map((reason) => <li key={reason}>{reason}</li>)}
                        </ul>
                      ) : (
                        <div className="text-xs text-terminal-muted">No robustness reasons returned.</div>
                      )}
                    </div>
                  </div>
                </TerminalPanel>
              </>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
