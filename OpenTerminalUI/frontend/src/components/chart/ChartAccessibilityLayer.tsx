type AccessibleChartRow = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
};

type Props = {
  summary: string;
  rows: AccessibleChartRow[];
  formatTime: (time: number | null) => string;
};

export function ChartAccessibilityLayer({ summary, rows, formatTime }: Props) {
  return (
    <>
      <div className="sr-only" aria-live="polite">
        {summary}
      </div>
      <details className="sr-only focus-within:not-sr-only focus-within:absolute focus-within:left-2 focus-within:top-14 focus-within:z-[80] focus-within:max-h-72 focus-within:w-[min(34rem,calc(100%-1rem))] focus-within:overflow-auto focus-within:rounded focus-within:border focus-within:border-terminal-border focus-within:bg-terminal-panel focus-within:p-2 focus-within:text-xs">
        <summary className="cursor-pointer text-terminal-accent">Chart data table</summary>
        <table className="mt-2 min-w-full text-left">
          <thead className="text-terminal-muted">
            <tr>
              <th className="px-1 py-1">Time</th>
              <th className="px-1 py-1 text-right">Open</th>
              <th className="px-1 py-1 text-right">High</th>
              <th className="px-1 py-1 text-right">Low</th>
              <th className="px-1 py-1 text-right">Close</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.time}>
                <td className="px-1 py-1">{formatTime(row.time)}</td>
                <td className="px-1 py-1 text-right">{row.open.toFixed(2)}</td>
                <td className="px-1 py-1 text-right">{row.high.toFixed(2)}</td>
                <td className="px-1 py-1 text-right">{row.low.toFixed(2)}</td>
                <td className="px-1 py-1 text-right">{row.close.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}
