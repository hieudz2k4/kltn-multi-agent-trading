import { SavedViewsControl } from "../components/savedViews/SavedViewsControl";
import { TerminalPanel } from "../components/terminal/TerminalPanel";

export function SavedViewsPage() {
  return (
    <div className="space-y-3 p-4">
      <TerminalPanel title="Saved Views" subtitle="Workspace snapshots">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-terminal-muted">
            Save and restore page filters, selected ticker, active tabs, chart layout, table state, and shell preset from supported workflow pages.
          </p>
          <SavedViewsControl pageLabel="Workspace" />
        </div>
      </TerminalPanel>
    </div>
  );
}
