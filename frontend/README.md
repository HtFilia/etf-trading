# Frontend (React + Vite + Recharts)

A small React app that connects to the backend WebSocket and renders a live ETF table with quick charts. Styling uses Tailwind via the Vite plugin.

## What it shows

- **Connectivity** badge and last message timestamp.
- **ETF table** with last, mid, diff (bps vs. band), and breach side.
- **Chart modal** when selecting a row – local history is built in memory.

## Project structure

```
src/
  components/
    EtfTable.jsx       # main table view
    ChartModal.jsx     # per-symbol chart modal (Recharts)
    ConnBadge.jsx      # WS status
    Header.jsx, WsUrlBadge.jsx
  hooks/
    useWsFeed.js       # robust WS hook w/ backoff & format handling
    useRecencySeries.js
  utils/
    format.js, sampling.js
  App.jsx, main.jsx, index.css, App.css
```

## Dev loop

1) Install deps

```bash
npm install
```

2) Run the dev server

```bash
npm run dev
```

Open the printed URL (e.g., <http://localhost:5173>).

> The page tries to connect to `ws://localhost:9080/stream` by default. You can override with a query param:  
> `http://localhost:5173/?ws=ws://127.0.0.1:9080/stream`

## Expected WebSocket message shape

Each frame is JSON with a `type`, an optional `ts` (ms), and a `payload` object. Known `type` prefixes: `prices.`, `fx.`, `inav.`. The UI only needs a subset (`prices.tick`, `inav.tick`).

## Lint / build

```bash
npm run lint
npm run build
npm run preview
```

## Troubleshooting

- If the **Conn** badge stays red, confirm the backend gateway is up and reachable and that CORS/WS is not blocked by proxies (use direct localhost in dev).
- For remote backends, pass `?ws=wss://host/stream` and ensure TLS termination is configured upstream.
