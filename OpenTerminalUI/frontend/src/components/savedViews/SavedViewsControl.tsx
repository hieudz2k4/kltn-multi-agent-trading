import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { createSavedView, deleteSavedView, listSavedViews, updateSavedView, type SavedView, type SavedViewPayload } from "../../api/client";
import { useStockStore } from "../../store/stockStore";
import { WORKSPACE_PRESET_STORAGE_KEY, readWorkspacePreset } from "../../workspace/presets";
import { TerminalButton } from "../terminal/TerminalButton";

const CAPTURE_STORAGE_KEYS = [
  WORKSPACE_PRESET_STORAGE_KEY,
  "ot:launchpad:layouts:v1",
  "ot:launchpad:active:v1",
  "ot:chart-workstation:v3",
  "ot:chart-workstation:snapshots:v1",
  "ot:backtesting:workspace:v1",
  "ot:portfolio:view:v1",
  "ot:screener:view:v1",
];
const PENDING_SAVED_VIEW_KEY = "ot:saved-view:pending";

function readStorageSnapshot(): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const key of CAPTURE_STORAGE_KEYS) {
    try {
      const raw = localStorage.getItem(key);
      if (raw == null) continue;
      out[key] = JSON.parse(raw);
    } catch {
      out[key] = localStorage.getItem(key);
    }
  }
  return out;
}

function restoreStorageSnapshot(storage: Record<string, unknown> | undefined) {
  if (!storage) return;
  for (const [key, value] of Object.entries(storage)) {
    try {
      localStorage.setItem(key, typeof value === "string" ? value : JSON.stringify(value));
    } catch {
      // Ignore storage failures and still restore route-level state.
    }
  }
}

function pageScope(pathname: string): string {
  if (pathname.includes("screener")) return "screener";
  if (pathname.includes("chart-workstation")) return "chart-workstation";
  if (pathname.includes("backtesting")) return "backtesting";
  if (pathname.includes("cockpit")) return "cockpit";
  if (pathname.includes("portfolio")) return "portfolio";
  return "workspace";
}

export function SavedViewsControl({ pageLabel, capture }: { pageLabel: string; capture?: () => Partial<SavedViewPayload> }) {
  const location = useLocation();
  const navigate = useNavigate();
  const ticker = useStockStore((s) => s.ticker);
  const setTicker = useStockStore((s) => s.setTicker);
  const [views, setViews] = useState<SavedView[]>([]);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState("");
  const scope = useMemo(() => pageScope(location.pathname), [location.pathname]);

  async function refresh() {
    try {
      setViews(await listSavedViews({ scope }));
    } catch {
      setViews([]);
    }
  }

  useEffect(() => {
    void refresh();
  }, [scope]);

  async function saveView() {
    const name = window.prompt("Saved view name", `${pageLabel} ${new Date().toLocaleString()}`);
    if (!name?.trim()) return;
    const extra = capture?.() ?? {};
    const payload: SavedViewPayload = {
      page: location.pathname,
      search: location.search,
      selectedTicker: ticker,
      shellPreset: readWorkspacePreset(),
      storage: readStorageSnapshot(),
      ...extra,
    };
    try {
      await createSavedView({ name: name.trim(), scope, page: location.pathname, payload });
      setStatus("Saved");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Save failed");
    }
  }

  function applyView(view: SavedView) {
    restoreStorageSnapshot(view.payload.storage);
    if (view.payload.shellPreset) {
      localStorage.setItem(WORKSPACE_PRESET_STORAGE_KEY, JSON.stringify(view.payload.shellPreset));
    }
    if (view.payload.selectedTicker) {
      setTicker(String(view.payload.selectedTicker).toUpperCase());
    }
    try {
      localStorage.setItem(PENDING_SAVED_VIEW_KEY, JSON.stringify(view.payload));
    } catch {
      // ignore
    }
    const target = `${view.payload.page || view.page}${view.payload.search || ""}`;
    navigate(target);
    window.dispatchEvent(new CustomEvent("ot:saved-view:apply", { detail: view.payload }));
    window.setTimeout(() => window.location.reload(), 50);
  }

  return (
    <div className="relative flex flex-wrap items-center gap-1">
      <TerminalButton size="sm" variant="accent" onClick={() => void saveView()}>
        Save view
      </TerminalButton>
      <TerminalButton size="sm" variant="default" onClick={() => setOpen((v) => !v)}>
        Saved views
      </TerminalButton>
      {status ? <span className="text-[11px] text-terminal-muted">{status}</span> : null}
      {open ? (
        <div className="absolute right-0 top-[calc(100%+4px)] z-50 w-80 rounded-sm border border-terminal-border bg-terminal-panel p-2 shadow-xl">
          <div className="mb-2 flex items-center justify-between">
            <div className="ot-type-panel-title text-terminal-accent">{pageLabel} Views</div>
            <button className="text-[11px] text-terminal-muted hover:text-terminal-text" onClick={() => setOpen(false)}>Close</button>
          </div>
          <div className="max-h-72 space-y-1 overflow-auto">
            {views.length === 0 ? <div className="text-xs text-terminal-muted">No saved views yet.</div> : null}
            {views.map((view) => (
              <div key={view.id} className="rounded-sm border border-terminal-border bg-terminal-bg p-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-semibold text-terminal-text">{view.name}</div>
                    <div className="text-[10px] text-terminal-muted">{new Date(view.updated_at).toLocaleString()}</div>
                  </div>
                  <div className="flex gap-1">
                    <button className="text-[10px] text-terminal-accent" onClick={() => applyView(view)}>Apply</button>
                    <button
                      className="text-[10px] text-terminal-muted hover:text-terminal-text"
                      onClick={async () => {
                        const name = window.prompt("Rename saved view", view.name);
                        if (!name?.trim()) return;
                        await updateSavedView(view.id, { name: name.trim() });
                        await refresh();
                      }}
                    >
                      Rename
                    </button>
                    <button
                      className="text-[10px] text-terminal-neg"
                      onClick={async () => {
                        if (!window.confirm(`Delete ${view.name}?`)) return;
                        await deleteSavedView(view.id);
                        await refresh();
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
