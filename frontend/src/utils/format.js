// Formatting, math, and small helpers shared across the app

export const now = () => Date.now();
export const toMs = (t) => (typeof t === "number" ? t : Date.parse(t));

export const fmtTs = (ts) =>
  ts ? new Date(ts).toLocaleTimeString() : "–";

export const fmtN = (x, maxFrac = 4) =>
  x == null || Number.isNaN(x)
    ? "–"
    : Number(x).toLocaleString(undefined, { maximumFractionDigits: maxFrac });

export const toBps = (x) =>
  x == null || !Number.isFinite(x) ? null : x * 1e4;

export const classNames = (...xs) => xs.filter(Boolean).join(" ");

// last vs iNAV & band status
export function computeMetrics(row) {
  const { lastPrice, inav, bandUpper, bandLower } = row || {};
  if (inav == null || lastPrice == null)
    return { diffBps: null, insideBand: null, breachSide: null };

  const rel = (lastPrice - inav) / inav;
  const diffBps = toBps(rel);

  let insideBand = null,
    breachSide = null;
  if (bandUpper != null && bandLower != null) {
    insideBand = lastPrice <= bandUpper && lastPrice >= bandLower;
    breachSide = insideBand ? null : lastPrice > bandUpper ? "above" : "below";
  }
  return { diffBps, insideBand, breachSide };
}
