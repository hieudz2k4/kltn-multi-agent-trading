import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Copy, Download, FileCode2, Play } from "lucide-react";

import {
  fetchStrategyPresets,
  generateStrategy,
  type StrategyExportFormat,
  type StrategyGenerateResponse,
  type StrategyPreset,
} from "../api/strategyExport";
import { extractApiErrorMessage } from "../api/base";
import { TerminalBadge } from "../components/terminal/TerminalBadge";
import { TerminalButton } from "../components/terminal/TerminalButton";
import { TerminalPanel } from "../components/terminal/TerminalPanel";

const FORMAT_LABELS: Record<StrategyExportFormat, string> = {
  pine: "Pine Script v6",
  mql5: "MT5 MQL5",
};

function downloadCode(result: StrategyGenerateResponse) {
  if (typeof URL.createObjectURL !== "function") return;
  const blob = new Blob([result.code], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = result.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function StrategyExportPage() {
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [format, setFormat] = useState<StrategyExportFormat>("pine");
  const [result, setResult] = useState<StrategyGenerateResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const presetsQuery = useQuery({
    queryKey: ["strategy-export", "presets"],
    queryFn: fetchStrategyPresets,
  });

  const presets = presetsQuery.data?.presets ?? [];
  const selectedPreset = useMemo<StrategyPreset | null>(
    () => presets.find((preset) => preset.id === selectedPresetId) ?? presets[0] ?? null,
    [presets, selectedPresetId],
  );

  useEffect(() => {
    if (!selectedPresetId && presets.length) {
      setSelectedPresetId(presets[0].id);
    }
  }, [presets, selectedPresetId]);

  const generateMutation = useMutation({
    mutationFn: generateStrategy,
    onSuccess: (next) => {
      setResult(next);
      setCopied(false);
    },
  });

  const runGenerate = (preset = selectedPreset, nextFormat = format) => {
    if (!preset) return;
    generateMutation.mutate({ spec: preset.spec, format: nextFormat });
  };

  const selectPreset = (preset: StrategyPreset) => {
    setSelectedPresetId(preset.id);
    runGenerate(preset, format);
  };

  const selectFormat = (nextFormat: StrategyExportFormat) => {
    setFormat(nextFormat);
    runGenerate(selectedPreset, nextFormat);
  };

  const copyCode = async () => {
    if (!result?.code || !navigator.clipboard?.writeText) return;
    await navigator.clipboard.writeText(result.code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  };

  const error = presetsQuery.error || generateMutation.error;
  const errorMessage = error ? extractApiErrorMessage(error, "Strategy export request failed.") : "";

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top_left,rgba(255,107,0,0.08),transparent_34rem)] p-3 md:p-5">
      <main className="mx-auto flex w-full max-w-[1680px] flex-col gap-4">
        <section className="rounded-md border border-terminal-border/70 bg-terminal-panel/95 p-4 md:p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <div className="mb-2 flex flex-wrap gap-2">
                <TerminalBadge variant="accent">Strategy Export</TerminalBadge>
                <TerminalBadge variant="neutral">{presets.length} presets</TerminalBadge>
                {result ? <TerminalBadge variant="info">{result.language}</TerminalBadge> : null}
              </div>
              <h1 className="font-sans text-2xl font-semibold tracking-normal text-terminal-text md:text-3xl">
                Generate deployable strategy code.
              </h1>
              <p className="mt-2 max-w-3xl font-sans text-sm leading-6 text-terminal-muted">
                Pick a vetted strategy spec, choose Pine Script or MQL5, then copy or download the generated source.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {(["pine", "mql5"] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  className={[
                    "rounded-sm border px-3 py-2 text-xs uppercase tracking-wide outline-none focus-visible:ring-1 focus-visible:ring-terminal-accent/50",
                    format === item
                      ? "border-terminal-accent bg-terminal-accent/15 text-terminal-accent"
                      : "border-terminal-border text-terminal-muted hover:text-terminal-text",
                  ].join(" ")}
                  onClick={() => selectFormat(item)}
                >
                  {FORMAT_LABELS[item]}
                </button>
              ))}
            </div>
          </div>
        </section>

        {errorMessage ? (
          <div className="rounded-sm border border-terminal-neg/70 bg-terminal-neg/10 px-3 py-2 text-xs text-terminal-neg">
            {errorMessage}
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
          <TerminalPanel title="Preset Library" subtitle="Select a strategy spec">
            <div className="max-h-[68vh] space-y-2 overflow-auto pr-1">
              {presetsQuery.isLoading ? <div className="text-xs text-terminal-muted">Loading presets...</div> : null}
              {!presetsQuery.isLoading && !presets.length ? <div className="text-xs text-terminal-muted">No strategy presets returned.</div> : null}
              {presets.map((preset) => {
                const active = selectedPreset?.id === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    className={[
                      "w-full rounded-sm border p-3 text-left outline-none transition-colors focus-visible:ring-1 focus-visible:ring-terminal-accent/50",
                      active
                        ? "border-terminal-accent bg-terminal-accent/10"
                        : "border-terminal-border bg-terminal-bg/40 hover:border-terminal-accent/60",
                    ].join(" ")}
                    onClick={() => selectPreset(preset)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 font-semibold text-terminal-text">{preset.name}</div>
                      {active ? <TerminalBadge variant="accent">Active</TerminalBadge> : null}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-terminal-muted">{preset.description}</div>
                  </button>
                );
              })}
            </div>
          </TerminalPanel>

          <TerminalPanel
            title="Generated Code"
            subtitle={result?.filename ?? "Generate a preset to preview source"}
            actions={
              <div className="flex flex-wrap gap-2">
                <TerminalButton
                  type="button"
                  size="sm"
                  variant="accent"
                  loading={generateMutation.isPending}
                  disabled={!selectedPreset}
                  leftIcon={<Play className="h-3 w-3" />}
                  onClick={() => runGenerate()}
                >
                  Generate
                </TerminalButton>
                <TerminalButton type="button" size="sm" variant="default" disabled={!result?.code} leftIcon={<Copy className="h-3 w-3" />} onClick={copyCode}>
                  {copied ? "Copied" : "Copy"}
                </TerminalButton>
                <TerminalButton
                  type="button"
                  size="sm"
                  variant="default"
                  disabled={!result?.code}
                  leftIcon={<Download className="h-3 w-3" />}
                  onClick={() => result && downloadCode(result)}
                >
                  Download
                </TerminalButton>
              </div>
            }
          >
            {result?.warnings?.length ? (
              <div className="mb-3 rounded-sm border border-terminal-warn/70 bg-terminal-warn/10 px-3 py-2 text-xs text-terminal-warn">
                {result.warnings.map((warning) => (
                  <div key={warning}>{warning}</div>
                ))}
              </div>
            ) : null}

            {generateMutation.isPending ? (
              <div className="flex min-h-[52vh] items-center justify-center gap-2 text-xs text-terminal-muted">
                <FileCode2 className="h-4 w-4" />
                Generating {FORMAT_LABELS[format]}...
              </div>
            ) : result?.code ? (
              <pre className="max-h-[68vh] overflow-auto rounded-sm border border-terminal-border bg-terminal-bg p-3 text-[11px] leading-5 text-terminal-text">
                <code>{result.code}</code>
              </pre>
            ) : (
              <div className="flex min-h-[52vh] items-center justify-center rounded-sm border border-dashed border-terminal-border/80 p-6 text-center text-xs text-terminal-muted">
                Select a preset and generate code for the chosen export target.
              </div>
            )}
          </TerminalPanel>
        </div>
      </main>
    </div>
  );
}
