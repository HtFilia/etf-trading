import React, { useEffect, useMemo, useRef, useState } from "react";

/**
 * ETF Market Making Dashboard – MVP
 * ------------------------------------------------------------
 * - Connects to ws://localhost:9080/stream (override via ?ws=ws://...)
 * - Consumes ZeroMQ-bridged topics (e.g., prices.tick, inav.tick, fx.spot)
 * - Displays live ETF price vs iNAV with bps diff and band check
 * - Graceful reconnect with exponential backoff + connection status
 * - Clean, modern UI using Tailwind (no external CSS needed)
 *
 * Assumed message shapes (robust to extras):
 * {
 *   topic: "prices.tick" | "inav.tick" | "fx.spot" | "fx.forwards" | string,
 *   ts: number | string,                         // epoch ms or ISO
 *   data: {
 *     symbol?: string,                           // ETF ticker (e.g., SPY, CAC)
 *     price?: number,
 *     inav?: number,
 *     band_upper?: number,
 *     band_lower?: number,
 *     // ... other fields ignored for UI
 *   }
 * }
 */

// ---------- Types (lightweight, JS-doc style) ----------
/** @typedef {{
 *  lastPrice?: number;
 *  inav?: number;
 *  bandUpper?: number;
 *  bandLower?: number;
 *  lastTs?: number;           // ms epoch for most recent update (any source)
 *  priceTs?: number;          // last price tick time
 *  inavTs?: number;           // last inav tick time
 * }} InstrumentRow
 */

// ---------- Utilities ----------
const now = () => Date.now();
const toMs = (t) => (typeof t === "number" ? t : Date.parse(t));
const fmtTs = (ts) => (ts ? new Date(ts).toLocaleTimeString() : "–");
const fmt2 = (x) => (x == null || Number.isNaN(x) ? "–" : x.toLocaleString(undefined, { maximumFractionDigits: 2 }));
const toBps = (x) => (x == null || !Number.isFinite(x) ? null : x * 1e4);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const classNames = (...xs) => xs.filter(Boolean).join(" ");

// Compute diff vs iNAV and band assessment
function computeMetrics(row /** @type {InstrumentRow} */) {
  const { lastPrice, inav, bandUpper, bandLower } = row || {};
  if (inav == null || lastPrice == null) {
    return { diffBps: null, insideBand: null, breachSide: null };
  }
  const rel = (lastPrice - inav) / inav; // e.g., 0.001 = +10 bps
  const diffBps = toBps(rel);

  let insideBand = null;
  let breachSide = null;
  if (bandUpper != null && bandLower != null) {
    insideBand = lastPrice <= bandUpper && lastPrice >= bandLower;
    if (!insideBand) {
      breachSide = lastPrice > bandUpper ? "above" : "below";
    }
  }
  return { diffBps, insideBand, breachSide };
}

// ---------- Main Component ----------
export default function App() {
  const [rows, setRows] = useState(/** @type {Record<string, InstrumentRow>} */({}));
  const [status, setStatus] = useState(/** @type {"connecting"|"open"|"closing"|"closed"} */("connecting"));
  const [lastAnyTs, setLastAnyTs] = useState(/** @type {number|undefined} */(undefined));

  const wsRef = useRef(/** @type {WebSocket | null} */(null));
  const backoffRef = useRef({ attempt: 0, timer: /** @type {any} */(null) });
  const isUnmounted = useRef(false);

  // Resolve WS URL (allow override via query string)
  const wsUrl = useMemo(() => {
    const url = new URL(window.location.href);
    return url.searchParams.get("ws") || "ws://localhost:9080/stream";
  }, []);

  // Connection & Reconnect logic
  useEffect(() => {
    function connect() {
      clearTimeout(backoffRef.current.timer);
      setStatus("connecting");
      try {
        wsRef.current = new WebSocket(wsUrl);
      } catch (err) {
        scheduleReconnect();
        return;
      }

      const ws = wsRef.current;

      ws.onopen = () => {
        setStatus("open");
        backoffRef.current.attempt = 0; // reset backoff
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          const topic = msg.topic || msg.type || "";
          const ts = msg.ts != null ? toMs(msg.ts) : now();
          setLastAnyTs(ts);

          if (topic.startsWith("prices.")) {
            const sym = msg.data?.symbol || msg.symbol || msg.data?.etf || "UNKNOWN";
            const price = Number(msg.data?.price ?? msg.price ?? NaN);
            if (!sym || !Number.isFinite(price)) return;

            setRows((prev) => ({
              ...prev,
              [sym]: {
                ...(prev[sym] || {}),
                lastPrice: price,
                lastTs: Math.max(ts, prev[sym]?.lastTs || 0),
                priceTs: ts,
              },
            }));
          } else if (topic.startsWith("inav.")) {
            const sym = msg.data?.symbol || msg.symbol || msg.data?.etf || "UNKNOWN";
            const inav = Number(msg.data?.inav ?? msg.inav ?? NaN);
            const bandU = Number(msg.data?.band_upper ?? msg.band_upper ?? NaN);
            const bandL = Number(msg.data?.band_lower ?? msg.band_lower ?? NaN);
            if (!sym || !Number.isFinite(inav)) return;

            setRows((prev) => ({
              ...prev,
              [sym]: {
                ...(prev[sym] || {}),
                inav,
                bandUpper: Number.isFinite(bandU) ? bandU : prev[sym]?.bandUpper,
                bandLower: Number.isFinite(bandL) ? bandL : prev[sym]?.bandLower,
                lastTs: Math.max(ts, prev[sym]?.lastTs || 0),
                inavTs: ts,
              },
            }));
          } else {
            // fx.* or other topics: we don't display yet but keep heartbeat fresh
          }
        } catch (e) {
          // ignore bad JSON
        }
      };

      ws.onclose = () => {
        setStatus("closed");
        scheduleReconnect();
      };

      ws.onerror = () => {
        // Let onclose handle reconnection
        try { ws.close(); } catch {}
      };
    }

    function scheduleReconnect() {
      if (isUnmounted.current) return;
      const a = backoffRef.current.attempt + 1;
      backoffRef.current.attempt = a;
      const delay = Math.min(30000, Math.round((2 ** a) * 250)); // 250ms, 500ms, 1s, ... up to 30s
      clearTimeout(backoffRef.current.timer);
      backoffRef.current.timer = setTimeout(connect, delay);
    }

    connect();
    return () => {
      isUnmounted.current = true;
      clearTimeout(backoffRef.current.timer);
      setStatus("closing");
      try { wsRef.current?.close(); } catch {}
    };
  }, [wsUrl]);

  // Derived table data
  const table = useMemo(() => {
    const entries = Object.entries(rows).map(([sym, row]) => {
      const { diffBps, insideBand, breachSide } = computeMetrics(row);
      return { symbol: sym, ...row, diffBps, insideBand, breachSide };
    });

    // Sort: freshest first, then alpha
    entries.sort((a, b) => (b.lastTs ?? 0) - (a.lastTs ?? 0) || a.symbol.localeCompare(b.symbol));
    return entries;
  }, [rows]);

  // Staleness indicator
  const staleSeconds = useMemo(() => (lastAnyTs ? Math.max(0, (now() - lastAnyTs) / 1000) : null), [lastAnyTs]);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="sticky top-0 z-10 backdrop-blur bg-zinc-950/70 border-b border-zinc-800">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-2xl bg-zinc-800 grid place-items-center shadow-inner">
              <span className="text-sm">ETF</span>
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">AMM Dashboard · MVP</h1>
              <p className="text-xs text-zinc-400">Live ETF vs iNAV · 1s ticks</p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-sm">
            <ConnBadge status={status} />
            <div className="hidden sm:block text-zinc-400">
              {staleSeconds == null ? "–" : `last tick ${staleSeconds.toFixed(1)}s ago`}
            </div>
            <WsUrlBadge url={wsUrl} />
          </div>
        </div>
      </header>

      {/* Table */}
      <main className="max-w-7xl mx-auto p-4">
        <div className="overflow-hidden rounded-2xl border border-zinc-800 shadow-lg bg-zinc-900/40">
          <div className="grid grid-cols-12 px-4 py-2 text-xs uppercase tracking-wide text-zinc-400 border-b border-zinc-800">
            <div className="col-span-2">ETF</div>
            <div className="col-span-2 text-right">Last</div>
            <div className="col-span-2 text-right">iNAV</div>
            <div className="col-span-2 text-right">Diff (bps)</div>
            <div className="col-span-2 text-center">Band</div>
            <div className="col-span-2 text-right">Updated</div>
          </div>

          {table.length === 0 ? (
            <div className="p-6 text-sm text-zinc-400">Waiting for data…</div>
          ) : (
            <ul className="divide-y divide-zinc-800">
              {table.map((r) => (
                <li key={r.symbol} className="grid grid-cols-12 px-4 py-3 hover:bg-zinc-900/60">
                  <div className="col-span-2 flex items-center gap-2">
                    <span className="font-medium">{r.symbol}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">{r.bandUpper != null && r.bandLower != null ? "band" : "–"}</span>
                  </div>

                  <div className="col-span-2 text-right tabular-nums">{fmt2(r.lastPrice)}</div>
                  <div className="col-span-2 text-right tabular-nums text-zinc-300">{fmt2(r.inav)}</div>

                  <div className={classNames(
                    "col-span-2 text-right tabular-nums",
                    r.diffBps == null ? "text-zinc-400" : r.diffBps > 0 ? "text-emerald-400" : "text-red-400"
                  )}>
                    {r.diffBps == null ? "–" : r.diffBps.toFixed(1)}
                  </div>

                  <div className="col-span-2 flex items-center justify-center">
                    {r.insideBand == null ? (
                      <span className="text-zinc-400">–</span>
                    ) : r.insideBand ? (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 text-xs">inside</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full bg-red-500/10 text-red-300 text-xs">{r.breachSide}</span>
                    )}
                  </div>

                  <div className="col-span-2 text-right text-zinc-400 tabular-nums">{fmtTs(r.lastTs)}</div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Hints */}
        <div className="mt-4 text-xs text-zinc-500 leading-relaxed">
          <p>
            Tip: pass <code className="px-1 py-0.5 bg-zinc-800 rounded">?ws=ws://localhost:9080/stream</code> in the URL to override the WebSocket endpoint.
          </p>
          <p className="mt-1">
            Expected topics: <code className="px-1 py-0.5 bg-zinc-800 rounded">prices.*</code> and <code className="px-1 py-0.5 bg-zinc-800 rounded">inav.*</code> with <code className="px-1 py-0.5 bg-zinc-800 rounded">symbol</code>, <code className="px-1 py-0.5 bg-zinc-800 rounded">price</code>, <code className="px-1 py-0.5 bg-zinc-800 rounded">inav</code>, and optional <code className="px-1 py-0.5 bg-zinc-800 rounded">band_upper</code>/<code className="px-1 py-0.5 bg-zinc-800 rounded">band_lower</code>.
          </p>
        </div>
      </main>
    </div>
  );
}

function ConnBadge({ status }) {
  const color = status === "open" ? "bg-emerald-500" : status === "connecting" ? "bg-amber-500" : "bg-red-500";
  const label = status === "open" ? "connected" : status === "connecting" ? "connecting" : "disconnected";
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={classNames("inline-block h-2.5 w-2.5 rounded-full", color)} />
      <span className="text-zinc-300">{label}</span>
    </div>
  );
}

function WsUrlBadge({ url }) {
  return (
    <div className="px-2 py-1 rounded-lg bg-zinc-800 text-zinc-300 text-xs font-mono whitespace-nowrap max-w-[50vw] overflow-hidden text-ellipsis" title={url}>
      {url}
    </div>
  );
}
