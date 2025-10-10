import { useEffect, useRef, useState } from "react";
import { decimateRecency } from "../utils/sampling";

/**
 * Produces a decimated (recency-weighted) series for the selected symbol.
 * Throttles updates to ~2 Hz to avoid jitter.
 */
export default function useRecencySeries(histRef, selected) {
  const [series, setSeries] = useState([]);
  const lastFrameRef = useRef(0);

  useEffect(() => {
    if (!selected) return;
    const id = setInterval(() => {
      const nowT = Date.now();
      if (nowT - lastFrameRef.current < 500) return; // ~2 Hz
      lastFrameRef.current = nowT;

      const raw = histRef.current[selected] || [];
      // important: always pass a fresh array to Recharts
      setSeries(decimateRecency(raw));
    }, 200);
    return () => clearInterval(id);
  }, [histRef, selected]);

  useEffect(() => {
    if (!selected) {
      setSeries([]);
      return;
    }
    const raw = histRef.current[selected] || [];
    setSeries(decimateRecency(raw));
  }, [histRef, selected]);

  return series;
}
