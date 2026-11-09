import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { extractApiErrorMessage } from "../api/base";
import {
  ingestResearch,
  ingestUrlResearch,
  listResearch,
  searchResearch,
  type ResearchItem,
} from "../api/research";
import { TerminalButton } from "../components/terminal/TerminalButton";
import { TerminalInput } from "../components/terminal/TerminalInput";

function formatDate(value: string): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "2-digit" });
}

function formatChars(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k chars`;
  return `${value} chars`;
}

// Card styling mirrors the home screen (rounded border-terminal-border
// bg-terminal-panel/80 p-5, accent headings) so Research feels native.
function ResearchCard({ item }: { item: ResearchItem }) {
  return (
    <article className="group rounded border border-terminal-border bg-terminal-panel/80 p-5 backdrop-blur-[1px] hover:border-terminal-accent">
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="block text-sm font-semibold text-terminal-text hover:text-terminal-accent"
          >
            {item.title || "Untitled research item"}
          </a>
          <div className="mt-1 truncate text-xs text-terminal-muted">
            {(item.authors || []).length ? item.authors.join(", ") : "Unknown authors"}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-1 text-[10px] uppercase tracking-wide">
          {typeof item.score === "number" ? (
            <span className="rounded border border-terminal-accent/50 bg-terminal-accent/10 px-2 py-0.5 text-terminal-accent">
              Score {item.score.toFixed(3)}
            </span>
          ) : null}
          {item.source ? (
            <span className="rounded border border-terminal-border px-2 py-0.5 text-terminal-muted">
              {item.source}
            </span>
          ) : null}
          {item.text_chars && item.text_chars > 0 ? (
            <span className="rounded border border-terminal-pos/50 bg-terminal-pos/10 px-2 py-0.5 text-terminal-pos">
              {formatChars(item.text_chars)}
            </span>
          ) : null}
          <span className="rounded border border-terminal-border px-2 py-0.5 text-terminal-muted">
            {formatDate(item.published_at)}
          </span>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {(item.categories || []).slice(0, 8).map((category) => (
          <span key={`${item.id}-${category}`} className="rounded border border-terminal-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-terminal-muted">
            {category}
          </span>
        ))}
      </div>
      <p
        className="mt-3 overflow-hidden text-xs leading-5 text-terminal-muted"
        style={{ display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical" }}
      >
        {item.abstract || "No abstract available."}
      </p>
    </article>
  );
}

export function ResearchPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [ingestQuery, setIngestQuery] = useState("cat:q-fin.*");
  const [maxResults, setMaxResults] = useState(25);
  const [ingestUrl, setIngestUrl] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const recentQuery = useQuery({
    queryKey: ["research", "items"],
    queryFn: () => listResearch(),
  });

  const searchMutation = useMutation({
    mutationFn: (q: string) => searchResearch(q),
  });

  const ingestMutation = useMutation({
    mutationFn: () => ingestResearch(ingestQuery.trim() || "cat:q-fin.*", maxResults),
    onSuccess: async (result) => {
      setStatus(`Ingested ${result.ingested} of ${result.fetched}`);
      searchMutation.reset();
      await queryClient.invalidateQueries({ queryKey: ["research", "items"] });
    },
  });

  const ingestUrlMutation = useMutation({
    mutationFn: () => ingestUrlResearch(ingestUrl.trim()),
    onSuccess: async (result) => {
      setStatus(
        result.ingested
          ? `Added "${result.title || result.url}" (${result.text_chars.toLocaleString()} chars)`
          : "URL already indexed or returned no content",
      );
      setIngestUrl("");
      searchMutation.reset();
      await queryClient.invalidateQueries({ queryKey: ["research", "items"] });
    },
  });

  useEffect(() => {
    if (!status) return;
    const timeout = window.setTimeout(() => setStatus(null), 5000);
    return () => window.clearTimeout(timeout);
  }, [status]);

  const error = useMemo(() => {
    const candidate =
      recentQuery.error || searchMutation.error || ingestMutation.error || ingestUrlMutation.error;
    return candidate ? extractApiErrorMessage(candidate, "Research request failed.") : null;
  }, [ingestMutation.error, ingestUrlMutation.error, recentQuery.error, searchMutation.error]);

  const items = searchMutation.data?.results ?? recentQuery.data?.items ?? [];
  const isLoading =
    recentQuery.isLoading ||
    searchMutation.isPending ||
    ingestMutation.isPending ||
    ingestUrlMutation.isPending;
  const showingSearch = Boolean(searchMutation.data);

  return (
    <div className="flex h-full min-h-0 flex-col bg-terminal-bg font-mono text-terminal-text">
      {/* Header bar — mirrors the home screen header */}
      <div className="border-b border-terminal-border bg-terminal-panel px-4 py-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-lg font-semibold uppercase tracking-widest text-terminal-accent">Research</div>
            <div className="text-xs uppercase tracking-wide text-terminal-muted">Quant Knowledge Base &mdash; arXiv</div>
          </div>
          <div className="text-right text-xs uppercase tracking-wide text-terminal-muted">
            {items.length} indexed
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          {/* Controls card — home card styling */}
          <div className="rounded border border-terminal-border bg-terminal-panel/80 p-5 backdrop-blur-[1px]">
            <div className="text-sm font-semibold uppercase tracking-wide text-terminal-accent">Search &amp; Ingest</div>
            <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(18rem,1fr)_minmax(24rem,auto)]">
              <form
                className="grid gap-2 sm:grid-cols-[minmax(12rem,1fr)_auto]"
                onSubmit={(event) => {
                  event.preventDefault();
                  const q = searchTerm.trim();
                  if (q) searchMutation.mutate(q);
                }}
              >
                <TerminalInput value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search indexed papers" />
                <TerminalButton type="submit" variant="accent" loading={searchMutation.isPending} disabled={!searchTerm.trim()}>
                  Search
                </TerminalButton>
              </form>

              <form
                className="grid gap-2 sm:grid-cols-[minmax(10rem,1fr)_7rem_auto]"
                onSubmit={(event) => {
                  event.preventDefault();
                  ingestMutation.mutate();
                }}
              >
                <TerminalInput value={ingestQuery} onChange={(event) => setIngestQuery(event.target.value)} placeholder="cat:q-fin.*" />
                <TerminalInput
                  type="number"
                  min={1}
                  max={100}
                  value={maxResults}
                  onChange={(event) => setMaxResults(Math.max(1, Number(event.target.value) || 1))}
                />
                <TerminalButton type="submit" loading={ingestMutation.isPending}>
                  Ingest arXiv
                </TerminalButton>
              </form>

              <form
                className="grid gap-2 sm:grid-cols-[minmax(12rem,1fr)_auto] xl:col-span-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (ingestUrl.trim()) ingestUrlMutation.mutate();
                }}
              >
                <TerminalInput
                  value={ingestUrl}
                  onChange={(event) => setIngestUrl(event.target.value)}
                  placeholder="Add URL (article or PDF) to the knowledge base"
                />
                <TerminalButton type="submit" loading={ingestUrlMutation.isPending} disabled={!ingestUrl.trim()}>
                  Add URL
                </TerminalButton>
              </form>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wide text-terminal-muted">
              <span>{showingSearch ? `Results for ${searchMutation.data?.query || searchTerm}` : "Recent indexed papers"}</span>
              {status ? <span className="rounded border border-terminal-pos/50 bg-terminal-pos/10 px-2 py-0.5 text-terminal-pos">{status}</span> : null}
            </div>
            {error ? <div className="mt-2 rounded border border-terminal-neg bg-terminal-neg/10 px-2 py-1 text-xs text-terminal-neg">{error}</div> : null}
          </div>

          {/* Results grid — home card styling */}
          {isLoading && !items.length ? (
            <div className="rounded border border-terminal-border bg-terminal-panel/80 p-5 text-xs text-terminal-muted">Loading research&hellip;</div>
          ) : null}
          {!isLoading && !items.length ? (
            <div className="rounded border border-terminal-border bg-terminal-panel/80 p-5 text-center text-xs text-terminal-muted">
              No research indexed yet &mdash; ingest from arXiv to build the knowledge base.
            </div>
          ) : null}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {items.map((item) => (
              <ResearchCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
