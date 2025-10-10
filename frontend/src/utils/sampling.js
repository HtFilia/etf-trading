// Recency-weighted decimator:
// 0–2m: 1s, 2–10m: 5s, 10–60m: 30s, >60m: 5m

export function decimateRecency(arr) {
  if (!arr || arr.length === 0) return [];
  const nowT = Date.now();

  const TWO_MIN = 2 * 60 * 1000;
  const TEN_MIN = 10 * 60 * 1000;
  const ONE_HOUR = 60 * 60 * 1000;
  const ONE_SEC = 1000;
  const FIVE_SEC = 5 * 1000;
  const THIRTY_SEC = 30 * 1000;
  const FIVE_MIN = 5 * 60 * 1000;

  const rules = [
    { horizon: TWO_MIN, interval: ONE_SEC },
    { horizon: TEN_MIN, interval: FIVE_SEC },
    { horizon: ONE_HOUR, interval: THIRTY_SEC },
    { horizon: Infinity, interval: FIVE_MIN },
  ];

  const out = [];
  const lastKept = Array(rules.length).fill(Number.NaN);

  for (let i = 0; i < arr.length; i++) {
    const p = arr[i];
    const t = +p.t;
    if (!Number.isFinite(t)) continue;

    const age = nowT - t;
    let idx = 0;
    while (idx < rules.length && age > rules[idx].horizon) idx++;
    const interval = (rules[idx] || rules[rules.length - 1]).interval;

    if (
      !Number.isFinite(lastKept[idx]) ||
      t - lastKept[idx] >= interval ||
      i === arr.length - 1
    ) {
      out.push(p);
      lastKept[idx] = t;
    }
  }
  return out;
}
