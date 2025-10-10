import React, { useMemo, useState } from "react";
import useWsFeed from "./hooks/useWsFeed";
import useRecencySeries from "./hooks/useRecencySeries";
import Header from "./components/Header";
import EtfTable from "./components/EtfTable";
import ChartModal from "./components/ChartModal";
import { now } from "./utils/format";

export default function App() {
  const { rows, status, lastAnyTs, debug, wsUrl, histRef } = useWsFeed();
  const [selected, setSelected] = useState(null);
  const series = useRecencySeries(histRef, selected);

  const staleSeconds = useMemo(
    () => (lastAnyTs ? Math.max(0, (now() - lastAnyTs) / 1000) : null),
    [lastAnyTs]
  );

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <Header status={status} staleSeconds={staleSeconds} wsUrl={wsUrl} />

      <main className="max-w-7xl mx-auto p-4">
        <EtfTable rows={rows} onSelect={setSelected} />

        {/* Debug panel (optional – keep while developing) */}
        <div className="mt-4 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-3">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>WS Messages: <span className="text-zinc-200 font-mono">{debug.count}</span></span>
            <span>Last topic: <span className="text-zinc-200 font-mono">{debug.lastTopic}</span></span>
          </div>
          {debug.lastError && (
            <div className="mt-2 text-xs text-red-400">Last error: {debug.lastError}</div>
          )}
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-zinc-300 bg-zinc-950/50 p-2 rounded-lg">
{debug.lastRaw || "— no frames yet —"}
          </pre>
        </div>

        {selected && (
          <ChartModal symbol={selected} series={series} onClose={() => setSelected(null)} />
        )}
      </main>
    </div>
  );
}
