import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, BarChart3, Play, RefreshCw } from "lucide-react";

import {
  evaluateAlphaZoo,
  fetchAlphaZooFactors,
  type AlphaEvaluateResponse,
  type AlphaResultStatus,
} from "../api/alphaZoo";
import { extractApiErrorMessage } from "../api/base";
import { TerminalBadge } from "../components/terminal/TerminalBadge";
import { TerminalButton } from "../components/terminal/TerminalButton";
import { TerminalInput } from "../components/terminal/TerminalInput";
import { TerminalPanel } from "../components/terminal/TerminalPanel";

const DEFAULT_SYMBOLS = "AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, JPM";
const RANGES = ["6mo", "1y", "2y"] as const;

const statusTone: Record<AlphaResultStatus, string> = {
  alive: "border-terminal-pos bg-terminal-pos/10 text-terminal-pos",
  reversed: "border-terminal-warn bg-terminal-warn/10 text-terminal-warn",
  dead: "border-terminal-border bg-terminal-bg text-terminal-muted",
  insufficient: "border-terminal-border/70 bg-terminal-panel text-terminal-muted",
};

function parseSymbols(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
}

function fmt(value: number, digits = 3): string {
  return Number.isFinite(value) ? value.toFixed(digits) : "--";
}

function pct(value: number): string {
  if (!Number.isFinite(value)) return "--";
  return `${(value * 100).toFixed(1)}%`;
}

function MetricBar({ value, tone = "accent" }: { value: number; tone?: "accent" | "info" }) {
  const width = Math.min(100, Math.max(4, Math.abs(Number(value) || 0) * 100));
  const barClass = tone === "info" ? "bg-terminal-info" : "bg-terminal-accent";
  return (
    <div className="mt-1 h-1.5 w-20 rounded-sm bg-terminal-bg" aria-hidden="true">
      <div className={`h-full rounded-sm ${barClass}`} style={{ width: `${width}%` }} />
    </div>
  );
}

function StatusChip({ status }: { status: AlphaResultStatus }) {
  return (
    <span className={`inline-flex rounded-sm border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${statusTone[status]}`}>
      {status}
    </span>
  );
}

function ResultsTable({ evaluation }: { evaluation: AlphaEvaluateResponse | null }) {
  const rows = useMemo(
    () => [...(evaluation?.results ?? [])].sort((a, b) => Math.abs(b.rank_ic) - Math.abs(a.rank_ic)),
    [evaluation?.results],
  );

  if (!evaluation) {
    return (
      <div className="flex min-h-64 items-center justify-center rounded-sm border border-dashed border-terminal-border/80 p-6 text-center text-xs text-terminal-muted">
        Configure a basket, then run an evaluation to rank factor IC and stability.
      </div>
    );
  }

  if (!rows.length) {
    return (
      <div className="flex min-h-64 items-center justify-center rounded-sm border border-terminal-border p-6 text-center text-xs text-terminal-muted">
        No factor results returned for this basket and filter set.
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      <table className="min-w-[960px] w-full text-[11px]">
        <thead>
          <tr className="border-b border-terminal-border/70 text-terminal-muted">
            {["Factor", "Zoo", "Category", "IC", "IR", "Rank-IC", "Hit-rate", "Status"].map((header) => (
              <th key={header} className="px-2 py-2 text-left font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.factor_id} className="border-b border-terminal-border/30 hover:bg-terminal-bg/70">
              <td className="max-w-[260px] px-2 py-2">
                <div className="font-semibold text-terminal-text">{row.name}</div>
                <div className="truncate text-[10px] text-terminal-muted">{row.factor_id}</div>
              </td>
              <td className="px-2 py-2 text-terminal-accent">{row.zoo}</td>
              <td className="px-2 py-2 text-terminal-muted">{row.category}</td>
              <td className="px-2 py-2 text-terminal-text">
                {fmt(row.ic)}
                <MetricBar value={row.ic} />
              </td>
              <td className="px-2 py-2 text-terminal-text">
                {fmt(row.ir)}
                <MetricBar value={row.ir / 2} tone="info" />
              </td>
              <td className="px-2 py-2 font-semibold text-terminal-text">{fmt(row.rank_ic)}</td>
              <td className="px-2 py-2 text-terminal-text">{pct(row.hit_rate)}</td>
              <td className="px-2 py-2">
                <StatusChip status={row.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AlphaZooPage() {
  const [symbolsText, setSymbolsText] = useState(DEFAULT_SYMBOLS);
  const [range, setRange] = useState<(typeof RANGES)[number]>("1y");
  const [forwardDays, setForwardDays] = useState(5);
  const [selectedZoo, setSelectedZoo] = useState("all");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [evaluation, setEvaluation] = useState<AlphaEvaluateResponse | null>(null);

  const factorsQuery = useQuery({
    queryKey: ["alpha-zoo", "factors"],
    queryFn: fetchAlphaZooFactors,
  });

  const evaluateMutation = useMutation({
    mutationFn: evaluateAlphaZoo,
    onSuccess: setEvaluation,
  });

  const factors = factorsQuery.data?.factors ?? [];
  const zoos = factorsQuery.data?.zoos ?? [];
  const categories = useMemo(
    () => Array.from(new Set(factors.map((factor) => factor.category).filter(Boolean))).sort(),
    [factors],
  );
  const filteredFactors = useMemo(
    () =>
      factors.filter(
        (factor) =>
          (selectedZoo === "all" || factor.zoo === selectedZoo) &&
          (selectedCategory === "all" || factor.category === selectedCategory),
      ),
    [factors, selectedCategory, selectedZoo],
  );
  const groupedFactors = useMemo(() => {
    const groups = new Map<string, typeof filteredFactors>();
    for (const factor of filteredFactors) {
      groups.set(factor.zoo, [...(groups.get(factor.zoo) ?? []), factor]);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredFactors]);

  const runEvaluation = () => {
    const symbols = parseSymbols(symbolsText);
    if (!symbols.length) return;
    evaluateMutation.mutate({
      symbols,
      factor_ids: selectedZoo === "all" && selectedCategory === "all" ? undefined : filteredFactors.map((factor) => factor.id),
      zoo: selectedZoo === "all" ? undefined : selectedZoo,
      range,
      forward_days: forwardDays,
    });
  };

  const error = factorsQuery.error || evaluateMutation.error;
  const errorMessage = error ? extractApiErrorMessage(error, "Alpha Zoo request failed.") : "";
  const missing = evaluation?.coverage.missing ?? [];

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top_left,rgba(255,107,0,0.08),transparent_34rem)] p-3 md:p-5">
      <main className="mx-auto flex w-full max-w-[1680px] flex-col gap-4">
        <section className="rounded-md border border-terminal-border/70 bg-terminal-panel/95 p-4 md:p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <div className="mb-2 flex flex-wrap gap-2">
                <TerminalBadge variant="accent">Alpha Zoo</TerminalBadge>
                <TerminalBadge variant="neutral">{factors.length} factors</TerminalBadge>
                {evaluation ? <TerminalBadge variant="info">as of {evaluation.as_of}</TerminalBadge> : null}
              </div>
              <h1 className="font-sans text-2xl font-semibold tracking-normal text-terminal-text md:text-3xl">
                Rank formulaic factors by forward signal.
              </h1>
              <p className="mt-2 max-w-3xl font-sans text-sm leading-6 text-terminal-muted">
                Filter the zoo, evaluate a basket, then compare IC, IR, rank correlation, and hit-rate in one dense table.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs md:min-w-[420px]">
              <div className="rounded-md border border-terminal-border bg-terminal-bg/70 p-3">
                <div className="text-[11px] text-terminal-muted">Zoos</div>
                <div className="mt-1 text-xl font-semibold text-terminal-text">{zoos.length}</div>
              </div>
              <div className="rounded-md border border-terminal-border bg-terminal-bg/70 p-3">
                <div className="text-[11px] text-terminal-muted">Resolved</div>
                <div className="mt-1 text-xl font-semibold text-terminal-text">{evaluation?.coverage.resolved ?? "--"}</div>
              </div>
              <div className="rounded-md border border-terminal-border bg-terminal-bg/70 p-3">
                <div className="text-[11px] text-terminal-muted">Forward</div>
                <div className="mt-1 text-xl font-semibold text-terminal-text">{forwardDays}d</div>
              </div>
            </div>
          </div>
        </section>

        {errorMessage ? (
          <div className="rounded-sm border border-terminal-neg/70 bg-terminal-neg/10 px-3 py-2 text-xs text-terminal-neg">
            {errorMessage}
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="space-y-4">
            <TerminalPanel title="Evaluate" subtitle="Basket + horizon">
              <div className="space-y-3">
                <label className="block">
                  <span className="mb-1 block text-xs text-terminal-muted">Symbols</span>
                  <TerminalInput as="textarea" rows={3} value={symbolsText} onChange={(event) => setSymbolsText(event.target.value)} tone="ui" />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="block">
                    <span className="mb-1 block text-xs text-terminal-muted">Range</span>
                    <TerminalInput as="select" value={range} onChange={(event) => setRange(event.target.value as typeof range)} tone="ui">
                      {RANGES.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </TerminalInput>
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs text-terminal-muted">Forward days</span>
                    <TerminalInput
                      type="number"
                      min={1}
                      max={63}
                      value={forwardDays}
                      onChange={(event) => setForwardDays(Math.max(1, Number(event.target.value) || 1))}
                      tone="ui"
                    />
                  </label>
                </div>
                <TerminalButton
                  type="button"
                  variant="accent"
                  className="w-full"
                  loading={evaluateMutation.isPending}
                  disabled={factorsQuery.isLoading || !parseSymbols(symbolsText).length}
                  leftIcon={<Play className="h-3.5 w-3.5" />}
                  onClick={runEvaluation}
                >
                  Evaluate
                </TerminalButton>
              </div>
            </TerminalPanel>

            <TerminalPanel title="Zoo Browser" subtitle="Source + category filters">
              <div className="space-y-3">
                <TerminalInput as="select" value={selectedZoo} onChange={(event) => setSelectedZoo(event.target.value)} tone="ui" loading={factorsQuery.isLoading}>
                  <option value="all">All zoos</option>
                  {zoos.map((zoo) => (
                    <option key={zoo.id} value={zoo.id}>
                      {zoo.name} ({zoo.count})
                    </option>
                  ))}
                </TerminalInput>
                <TerminalInput as="select" value={selectedCategory} onChange={(event) => setSelectedCategory(event.target.value)} tone="ui" loading={factorsQuery.isLoading}>
                  <option value="all">All categories</option>
                  {categories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </TerminalInput>
                <div className="max-h-[42vh] space-y-3 overflow-auto pr-1">
                  {factorsQuery.isLoading ? <div className="text-xs text-terminal-muted">Loading factor catalog...</div> : null}
                  {!factorsQuery.isLoading && groupedFactors.length === 0 ? <div className="text-xs text-terminal-muted">No factors match these filters.</div> : null}
                  {groupedFactors.map(([zoo, items]) => (
                    <div key={zoo} className="border-t border-terminal-border/50 pt-2">
                      <div className="mb-2 flex items-center justify-between text-xs">
                        <span className="font-semibold text-terminal-text">{zoo}</span>
                        <span className="text-terminal-muted">{items.length}</span>
                      </div>
                      <div className="space-y-2">
                        {items.slice(0, 8).map((factor) => (
                          <div key={factor.id} className="rounded-sm border border-terminal-border/70 bg-terminal-bg/50 p-2">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0 font-semibold text-terminal-text">{factor.name}</div>
                              <span className="shrink-0 text-[10px] text-terminal-muted">{factor.window}d</span>
                            </div>
                            <div className="mt-1 line-clamp-2 text-[10px] leading-4 text-terminal-muted">{factor.description}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </TerminalPanel>
          </div>

          <TerminalPanel
            title="IC / IR Ranking"
            subtitle={evaluation ? `${evaluation.symbols.length} symbols / ${evaluation.results.length} factors` : "Sorted by absolute Rank-IC"}
            actions={
              evaluation ? (
                <TerminalButton type="button" size="sm" variant="ghost" leftIcon={<RefreshCw className="h-3 w-3" />} onClick={runEvaluation} loading={evaluateMutation.isPending}>
                  Refresh
                </TerminalButton>
              ) : null
            }
          >
            {missing.length ? (
              <div className="mb-3 flex gap-2 rounded-sm border border-terminal-warn/70 bg-terminal-warn/10 px-3 py-2 text-xs text-terminal-warn">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Missing symbols: {missing.join(", ")}</span>
              </div>
            ) : null}
            {evaluateMutation.isPending ? (
              <div className="flex min-h-64 items-center justify-center gap-2 text-xs text-terminal-muted">
                <BarChart3 className="h-4 w-4" />
                Evaluating factor signals...
              </div>
            ) : (
              <ResultsTable evaluation={evaluation} />
            )}
          </TerminalPanel>
        </div>
      </main>
    </div>
  );
}
