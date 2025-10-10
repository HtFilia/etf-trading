import { useEffect, useMemo, useRef, useState } from "react";
import { toMs } from "../utils/format";

/**
 * Maintains:
 * - rows (table data)
 * - histRef (full history per symbol with forward-fill)
 * - status / debug / lastAnyTs
 * - robust WS (NDJSON, Blob, ArrayBuffer), reconnection with backoff
 */

export default function useWsFeed() {
  const [rows, setRows] = useState({});
  const [status, setStatus] = useState("connecting");
  const [lastAnyTs, setLastAnyTs] = useState(undefined);
  const [debug, setDebug] = useState({
    count: 0,
    lastTopic: "-",
    lastRaw: "",
    lastError: "",
  });

  // Resolve WS URL (?ws=ws://host:port/stream), else smart default
  const wsUrl = useMemo(() => {
    const url = new URL(window.location.href);
    const override = url.searchParams.get("ws");
    if (override) return override;
    const isHttps = window.location.protocol === "https:";
    if (isHttps) {
      const host = window.location.host;
      return `wss://${host}/stream`;
    }
    return "ws://localhost:9080/stream";
  }, []);

  // Full history and latest snapshots to forward-fill
  const histRef = useRef({});   // { sym: [{ t, price?, inav?, bu?, bl? }] }
  const latestRef = useRef({}); // { sym: { price?, inav?, bu?, bl? } }

  function pushPoint(sym, t, patch) {
    const latest = latestRef.current[sym] || (latestRef.current[sym] = {});
    if (patch.price != null && Number.isFinite(patch.price)) latest.price = +patch.price;
    if (patch.inav  != null && Number.isFinite(patch.inav))  latest.inav  = +patch.inav;
    if (patch.bu    != null && Number.isFinite(patch.bu))    latest.bu    = +patch.bu;
    if (patch.bl    != null && Number.isFinite(patch.bl))    latest.bl    = +patch.bl;

    const point = { t: +t, price: latest.price, inav: latest.inav, bu: latest.bu, bl: latest.bl };
    const buf = histRef.current[sym] || (histRef.current[sym] = []);
    buf.push(point);

    // optional cap: ~2h @ 1s
    const MAX_POINTS = 2 * 60 * 60;
    if (buf.length > MAX_POINTS) buf.splice(0, buf.length - MAX_POINTS);
  }

  const wsRef = useRef(null);
  const backoffRef = useRef({ attempt: 0, timer: null });

  useEffect(() => {
    let cancelled = false;

    function scheduleReconnect(state, connectFn) {
      if (cancelled) return;
      const a = state.attempt + 1;
      state.attempt = a;
      const delay = Math.min(30000, Math.round(Math.pow(2, a) * 250)); // 250ms -> 30s
      clearTimeout(state.timer);
      state.timer = setTimeout(() => {
        if (!cancelled) connectFn();
      }, delay);
    }

    function connect() {
      clearTimeout(backoffRef.current.timer);
      setStatus("connecting");

      let ws;
      try {
        ws = new WebSocket(wsUrl);
      } catch (e) {
        setDebug((d) => ({ ...d, lastError: `constructor: ${String(e)}` }));
        setStatus("closed");
        scheduleReconnect(backoffRef.current, connect);
        return;
      }
      wsRef.current = ws;
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        if (cancelled) return;
        setStatus("open");
        backoffRef.current.attempt = 0;
        setDebug((d) => ({ ...d, lastError: "" }));
      };

      ws.onmessage = async (ev) => {
        try {
          let payload = ev.data;
          if (payload instanceof Blob) payload = await payload.text();
          if (payload instanceof ArrayBuffer)
            payload = new TextDecoder().decode(payload);
          const chunks =
            typeof payload === "string"
              ? payload.split(/\n+/).filter(Boolean)
              : [payload];

          for (const chunk of chunks) {
            const text = typeof chunk === "string" ? chunk : JSON.stringify(chunk);
            const msg = typeof chunk === "string" ? JSON.parse(chunk) : chunk;

            // Envelope normalization
            const topic = msg.topic || msg.type || msg.channel || "";
            const dataRaw =
              msg.data ??
              msg.payload ??
              (() => {
                const c = { ...msg };
                delete c.topic;
                delete c.type;
                delete c.channel;
                delete c.version;
                return c;
              })();
            const tsVal = dataRaw.ts ?? msg.ts ?? Date.now();
            const ts =
              typeof tsVal === "string" || typeof tsVal === "number"
                ? toMs(tsVal)
                : Date.now();

            setLastAnyTs(ts);
            setDebug((d) => ({
              ...d,
              count: d.count + 1,
              lastTopic: topic || "(none)",
              lastRaw: text.slice(0, 2000),
            }));

            // ---- Topic-specific handling ----
            if (topic.startsWith("prices.")) {
              // { security_id, bid, ask, mid, last, source }
              const sym =
                dataRaw.security_id ||
                dataRaw.symbol ||
                dataRaw.ticker ||
                "UNKNOWN";
              const price = Number(dataRaw.last ?? dataRaw.mid ?? dataRaw.price);
              if (sym && Number.isFinite(price)) {
                setRows((prev) => ({
                  ...prev,
                  [sym]: {
                    ...(prev[sym] || {}),
                    lastPrice: price,
                    lastTs: Math.max(ts, prev[sym]?.lastTs || 0),
                    priceTs: ts,
                  },
                }));
                pushPoint(sym, ts, { price });
              }
            } else if (topic.startsWith("inav.")) {
              // { etf_id|security_id|symbol, inav, band_upper?, band_lower?, ts? }
              const sym =
                dataRaw.etf_id ||
                dataRaw.security_id ||
                dataRaw.symbol ||
                dataRaw.ticker ||
                "UNKNOWN";
              const inav = Number(dataRaw.inav ?? dataRaw.value);
              const bandU = Number(dataRaw.band_upper ?? dataRaw.bandUpper);
              const bandL = Number(dataRaw.band_lower ?? dataRaw.bandLower);
              if (sym && Number.isFinite(inav)) {
                setRows((prev) => ({
                  ...prev,
                  [sym]: {
                    ...(prev[sym] || {}),
                    inav,
                    bandUpper: Number.isFinite(bandU)
                      ? bandU
                      : prev[sym]?.bandUpper,
                    bandLower: Number.isFinite(bandL)
                      ? bandL
                      : prev[sym]?.bandLower,
                    lastTs: Math.max(ts, prev[sym]?.lastTs || 0),
                    inavTs: ts,
                  },
                }));
                pushPoint(sym, ts, {
                  inav,
                  bu: Number.isFinite(bandU) ? bandU : undefined,
                  bl: Number.isFinite(bandL) ? bandL : undefined,
                });
              }
            } else if (topic === "fx.spot" || topic === "fx.forwards") {
              // reserved for future FX widgets
            }
          }
        } catch (e) {
          setDebug((d) => ({ ...d, lastError: `onmessage: ${String(e)}` }));
        }
      };

      ws.onerror = () => {
        setDebug((d) => ({ ...d, lastError: "onerror (see onclose)" }));
      };

      ws.onclose = (ev) => {
        if (cancelled) return;
        setStatus("closed");
        setDebug((d) => ({
          ...d,
          lastError: `onclose: code=${ev.code} reason=${
            ev.reason || "(no reason)"
          } wasClean=${ev.wasClean}`,
        }));
        scheduleReconnect(backoffRef.current, connect);
      };
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(backoffRef.current.timer);
      setStatus("closing");
      try {
        wsRef.current?.close();
      } catch {}
    };
  }, [wsUrl]);

  return { rows, status, lastAnyTs, debug, wsUrl, histRef };
}
