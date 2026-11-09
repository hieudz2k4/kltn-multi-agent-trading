import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { TerminalBadge } from "../../components/terminal/TerminalBadge";
import { TerminalPanel } from "../../components/terminal/TerminalPanel";
import { terminalColors } from "../../theme/terminal";

export type NewsSentimentOverviewProps = {
  overallLabel: "Bullish" | "Bearish" | "Neutral";
  averageScore: number;
  bullishPct: number;
  neutralPct: number;
  bearishPct: number;
  totalArticles: number;
  periodDays: number;
  dailySentiment: Array<{ date: string; avg_score: number; count: number }>;
  sectors: Array<{ sector: string; avg_sentiment: number }>;
  topSources: Array<{ source: string; count: number }>;
  keywordInput: string;
  onKeywordChange: (value: string) => void;
  keywordHits: Array<{ keyword: string; title: string; source: string; publishedAt: string }>;
};

function formatScore(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function sentimentVariant(label: NewsSentimentOverviewProps["overallLabel"]) {
  if (label === "Bullish") return "success";
  if (label === "Bearish") return "danger";
  return "neutral";
}

function sectorBackground(avgSentiment: number) {
  const alpha = Math.min(0.55, Math.abs(avgSentiment) + 0.1);

  if (avgSentiment > 0) return `rgba(34,197,94,${alpha})`;
  if (avgSentiment < 0) return `rgba(244,63,94,${alpha})`;
  return "#0D1117";
}

export function NewsSentimentOverview(props: NewsSentimentOverviewProps): JSX.Element {
  const {
    overallLabel,
    averageScore,
    bullishPct,
    neutralPct,
    bearishPct,
    totalArticles,
    periodDays,
    dailySentiment,
    sectors,
    topSources,
    keywordInput,
    onKeywordChange,
    keywordHits,
  } = props;

  return (
    <TerminalPanel title="Sentiment" subtitle={`${totalArticles} articles · ${periodDays}d`}>
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <TerminalBadge variant={sentimentVariant(overallLabel)}>{overallLabel}</TerminalBadge>
          <span className="text-sm font-semibold tabular-nums">{formatScore(averageScore)}</span>
        </div>

        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-terminal-muted">Distribution</div>
          <div className="h-2 w-full overflow-hidden rounded bg-terminal-bg">
            <div className="flex h-full w-full">
              <div style={{ width: `${bullishPct}%`, background: terminalColors.positive }} />
              <div style={{ width: `${neutralPct}%`, background: terminalColors.muted }} />
              <div style={{ width: `${bearishPct}%`, background: terminalColors.negative }} />
            </div>
          </div>
          <div className="mt-1 flex justify-between text-[11px] text-terminal-muted">
            <span>Bullish {bullishPct}%</span>
            <span>Neutral {neutralPct}%</span>
            <span>Bearish {bearishPct}%</span>
          </div>
        </div>

        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-terminal-muted">{periodDays}-day trend</div>
          <div className="h-28 w-full">
          {dailySentiment.length < 2 ? (
            <div className="flex h-full items-center justify-center rounded border border-dashed border-terminal-border text-[11px] text-terminal-muted">Not enough history yet</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dailySentiment}>
                <XAxis dataKey="date" hide />
                <YAxis domain={[-1, 1]} hide />
                <Tooltip
                  contentStyle={{
                    borderRadius: "4px",
                    border: `1px solid ${terminalColors.border}`,
                    background: terminalColors.panel,
                    color: terminalColors.text,
                  }}
                />
                <Line type="monotone" dataKey="avg_score" stroke={terminalColors.accent} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
          </div>
        </div>

        {sectors.length ? (
          <div className="grid grid-cols-2 gap-1 text-[11px] md:grid-cols-2">
            {sectors.slice(0, 8).map((row) => (
              <div
                key={row.sector}
                className="rounded border border-terminal-border px-1.5 py-1"
                style={{ background: sectorBackground(row.avg_sentiment) }}
              >
                <div className="truncate text-terminal-muted">{row.sector}</div>
                <div className="font-semibold">{formatScore(row.avg_sentiment)}</div>
              </div>
            ))}
          </div>
        ) : null}

        <div className="rounded border border-terminal-border bg-terminal-bg p-2">
          <div className="mb-1 text-[11px] text-terminal-muted">Keyword Alerts (comma separated)</div>
          <input
            value={keywordInput}
            onChange={(event) => onKeywordChange(event.target.value)}
            placeholder="FDA approval, CEO resign, acquisition"
            className="w-full rounded border border-terminal-border bg-terminal-panel px-2 py-1 text-xs outline-none focus:border-terminal-accent"
          />
          {keywordHits.length ? (
            <div className="mt-2 space-y-1">
              {keywordHits.map((hit, index) => (
                <div
                  key={`${hit.keyword}-${hit.publishedAt}-${index}`}
                  className="rounded border border-terminal-border bg-terminal-panel px-2 py-1 text-[11px]"
                >
                  <span className="text-terminal-accent">{hit.keyword}</span> | {hit.title}
                </div>
              ))}
            </div>
          ) : null}
        </div>

        {topSources.length ? (
          <div className="rounded border border-terminal-border bg-terminal-bg p-2">
            <div className="mb-1 text-[11px] text-terminal-muted">Top News Sources ({periodDays}d)</div>
            <div className="grid grid-cols-1 gap-1">
              {topSources.slice(0, 6).map((row) => (
                <div key={row.source} className="flex items-center justify-between rounded border border-terminal-border px-2 py-1 text-[11px]">
                  <span className="truncate">{row.source}</span>
                  <span className="text-terminal-muted">{row.count}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </TerminalPanel>
  );
}
