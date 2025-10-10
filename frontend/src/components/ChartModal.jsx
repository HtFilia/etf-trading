import { useEffect, useMemo, useRef } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { fmtN } from "../utils/format";

/**
 * Receives an already-decimated series.
 * - Sanitizes to numbers
 * - Computes sticky Y-domain from the decimated array
 * - Animations disabled
 */

export default function ChartModal({ symbol, series, onClose }) {
  const yDomainRef = useRef(null);
  useEffect(() => {
    yDomainRef.current = null;
  }, [symbol]);

  // fresh, numeric-only array for Recharts to avoid freeze/patch issues
  const chartData = useMemo(() => {
    const arr = series ? Array.from(series) : [];
    return arr
      .filter((p) => Number.isFinite(+p.t))
      .map((p) => ({
        t: +p.t,
        price: Number.isFinite(+p.price) ? +p.price : undefined,
        inav: Number.isFinite(+p.inav) ? +p.inav : undefined,
        bu: Number.isFinite(+p.bu) ? +p.bu : undefined,
        bl: Number.isFinite(+p.bl) ? +p.bl : undefined,
      }));
  }, [series]);

  const domain = useMemo(() => {
    if (!chartData || chartData.length === 0) return ["auto", "auto"];
    let min = Infinity,
      max = -Infinity;
    for (const p of chartData) {
      if (p.price != null) { if (p.price < min) min = p.price; if (p.price > max) max = p.price; }
      if (p.inav  != null) { if (p.inav  < min) min = p.inav;  if (p.inav  > max) max = p.inav;  }
      if (p.bu    != null) { if (p.bu    < min) min = p.bu;    if (p.bu    > max) max = p.bu;    }
      if (p.bl    != null) { if (p.bl    < min) min = p.bl;    if (p.bl    > max) max = p.bl;    }
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return ["auto", "auto"];
    const pad = (max - min) * 0.05 || 1e-6;
    const next = [min - pad, max + pad];
    if (!yDomainRef.current) yDomainRef.current = next;
    else {
      const [lo, hi] = yDomainRef.current;
      yDomainRef.current = [Math.min(lo, next[0]), Math.max(hi, next[1])];
    }
    return yDomainRef.current;
  }, [chartData]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Legend values reflect what's actually drawn (last point in decimated array)
  const last = chartData.length ? chartData[chartData.length - 1] : {};

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-5xl rounded-2xl bg-zinc-950 border border-zinc-800 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-3 border-b border-zinc-800 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{symbol} · Intraday</h2>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm"
          >
            Close
          </button>
        </div>

        <div className="p-5 h-[420px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="t"
                type="number"
                domain={["auto", "auto"]}
                tickFormatter={(t) => new Date(t).toLocaleTimeString()}
                minTickGap={24}
              />
              <YAxis domain={domain} allowDecimals />
              <Tooltip
                labelFormatter={(t) => new Date(t).toLocaleTimeString()}
                formatter={(v, name) => {
                  const label = { price: "Last", inav: "iNAV", bu: "Band Upper", bl: "Band Lower" }[name] || name;
                  return [fmtN(v, 4), label];
                }}
              />
              <Legend
                payload={[
                  { value: `Last: ${fmtN(last.price, 4)}`, type: "line", id: "price" },
                  { value: `iNAV: ${fmtN(last.inav, 4)}`, type: "line", id: "inav" },
                  { value: `Band U: ${fmtN(last.bu, 4)}`, type: "line", id: "bu" },
                  { value: `Band L: ${fmtN(last.bl, 4)}`, type: "line", id: "bl" },
                ]}
              />
              <Line type="monotone" dataKey="price" dot={false} strokeWidth={1.6} name="Last" isAnimationActive={false} />
              <Line type="monotone" dataKey="inav"  dot={false} strokeWidth={1.6} name="iNAV" isAnimationActive={false} />
              <Line type="monotone" dataKey="bu"    dot={false} strokeWidth={1}   name="Band Upper" isAnimationActive={false} />
              <Line type="monotone" dataKey="bl"    dot={false} strokeWidth={1}   name="Band Lower" isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
