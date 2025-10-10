import { computeMetrics, fmtN, fmtTs, classNames } from "../utils/format";

export default function EtfTable({ rows, onSelect }) {
  // Alphabetical rows for readability
  const entries = Object.entries(rows)
    .map(([symbol, row]) => {
      const { diffBps, insideBand, breachSide } = computeMetrics(row);
      return { symbol, ...row, diffBps, insideBand, breachSide };
    })
    .sort((a, b) => a.symbol.localeCompare(b.symbol));

  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-800 shadow-lg bg-zinc-900/40">
      <div className="grid grid-cols-12 px-4 py-2 text-xs uppercase tracking-wide text-zinc-400 border-b border-zinc-800">
        <div className="col-span-2">ETF</div>
        <div className="col-span-2 text-right">Last</div>
        <div className="col-span-2 text-right">iNAV</div>
        <div className="col-span-2 text-right">Diff (bps)</div>
        <div className="col-span-2 text-center">Band</div>
        <div className="col-span-2 text-right">Updated</div>
      </div>

      {entries.length === 0 ? (
        <div className="p-6 text-sm text-zinc-400">Waiting for data…</div>
      ) : (
        <ul className="divide-y divide-zinc-800">
          {entries.map((r) => (
            <li
              key={r.symbol}
              className="grid grid-cols-12 px-4 py-3 hover:bg-zinc-900/60 cursor-pointer"
              onClick={() => onSelect(r.symbol)}
            >
              <div className="col-span-2 flex items-center gap-2">
                <span className="font-medium">{r.symbol}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                  {r.bandUpper != null && r.bandLower != null ? "band" : "–"}
                </span>
              </div>

              <div className="col-span-2 text-right tabular-nums">{fmtN(r.lastPrice, 4)}</div>
              <div className="col-span-2 text-right tabular-nums text-zinc-300">{fmtN(r.inav, 4)}</div>

              <div
                className={classNames(
                  "col-span-2 text-right tabular-nums",
                  r.diffBps == null
                    ? "text-zinc-400"
                    : r.diffBps > 0
                    ? "text-emerald-400"
                    : "text-red-400"
                )}
              >
                {r.diffBps == null ? "–" : r.diffBps.toFixed(1)}
              </div>

              <div className="col-span-2 flex items-center justify-center">
                {r.insideBand == null ? (
                  <span className="text-zinc-400">–</span>
                ) : r.insideBand ? (
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 text-xs">
                    inside
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full bg-red-500/10 text-red-300 text-xs">
                    {r.breachSide}
                  </span>
                )}
              </div>

              <div className="col-span-2 text-right text-zinc-400 tabular-nums">{fmtTs(r.lastTs)}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
