# ETF Trading – Monorepo

This repository contains a **toy ETF trading stack** with a Python backend and a React (Vite) frontend. It streams simulated market data over WebSocket and renders a live table and charts in the browser. The goal is to demonstrate a clean, minimal end‑to‑end loop for market‑data distribution, lightweight pricing, and UI consumption.

> This is not production trading software. It’s an educational sandbox that shows service design, typed schemas, async I/O, and a reactive UI.

---

## What it does

- Simulates **market data** (equities/ETFs) and **FX** ticks.
- Computes simple **indicative NAV / pricing** from incoming ticks (toy logic).
- Publishes events on a **ZeroMQ** bus.
- Exposes a **WebSocket** gateway (`/stream`) that fans out bus events to browsers.
- React app subscribes and renders a live table + on‑demand charts.

---

## How it works (architecture)

```schema
[ simulation:market_data ]──┐
[ simulation:fx         ]───┼──>  ZMQ PUB  ──>  [ simulation:pricing ] ──> ZMQ PUB "inav.*"
                             │
                             └──>  topics: "prices.*", "fx.*"

                  ZMQ REQ/REP "pcf" (toy basket costs/lines)

[ gateway_ws ]  Starlette + Uvicorn
      └─ subscribes to: md_pub ("prices.*", "fx.*") and pricing_pub ("inav.*")
      └─ exposes: ws://{WS_HOST}:{WS_PORT}/stream  (JSON messages)

[ frontend ] React + Vite + Recharts
      └─ connects to the WebSocket and renders the live view
```

**Messaging:**  

- PUB/SUB sockets carry topic‑prefixed JSON (`prices.tick`, `fx.spot`, `inav.tick`, …).  
- REQ/REP provides a small **PCF** service (`apps/simulation/pcf.py`) for basket metadata/costs (toy).

**Key packages:** `pyzmq`, `pydantic v2`, `starlette`, `uvicorn`, `websockets`, `numpy (optional)`; frontend uses `react`, `vite`, `recharts`, `tailwindcss` via the Vite plugin.

---

## Repo layout

```tree
backend/
  apps/
    gateway_ws/      # WebSocket gateway (Starlette)
    simulation/      # fx, market_data, pricing, pcf toy services
  core/              # config, logging, schemas, zmq helpers, time calendar
  scripts/           # small probes (e.g., ws_probe.py)
frontend/            # React app (Vite)
.env.example         # minimal env to run everything locally
requirements.txt
Makefile             # helper targets (some are placeholders)
```

---

## Quickstart (minimal dev loop)

### 0) Prereqs

- **Python ≥ 3.11**
- **Node.js ≥ 18** (for Vite/React)
- **ZeroMQ**: we use `pyzmq` with **IPC (Unix domain sockets)** by default; most Linux/macOS work without extra steps.

On Windows, set `MD_PUB_ADDR`, etc., to TCP addresses (e.g., `tcp://127.0.0.1:6001`) in `.env` (IPC sockets aren’t supported on Windows).

### 1) Clone & env

```bash
cp .env.example .env
# (optionally tweak ZMQ_DIR, *ADDR, WS_HOST/PORT)
```

### 2) Backend (virtualenv + services)

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate  # Windows: backend\.venv\Scripts\activate
pip install -r requirements.txt
```

In **one terminal** (or tmux tab) per service, run:

```bash
# 2a) Market data simulator
python -m backend.apps.simulation.market_data

# 2b) FX simulator
python -m backend.apps.simulation.fx

# 2c) Pricing (consumes md_pub, publishes "inav.*")
python -m backend.apps.simulation.pricing

# 2d) PCF service (toy basket info, REQ/REP)
python -m backend.apps.simulation.pcf

# 2e) WebSocket gateway (Starlette+Uvicorn)
python -m backend.apps.gateway_ws.main
```

The gateway serves `ws://localhost:9080/stream` by default (from `.env`).

### 3) Frontend (Vite dev server)

```bash
cd frontend
npm install
npm run dev
```

Open the printed **local URL** (usually <http://localhost:5173>). The app will connect to the WebSocket (can also override via `?ws=ws://host:port/stream`).

### 4) Sanity check

- You should see rows of ETFs with last prices, bands, and a connectivity badge.  
- Click a row to view a modal chart rendered from the live history stored client‑side.

---

## Configuration

Variables (from `.env`, loaded via `backend/core/config.py`):

| Key                | Meaning                                  | Default in `.env.example`           |
|--------------------|-------------------------------------------|-------------------------------------|
| `DEV_MODE`         | Enables dev helpers/log shape             | `1`                                 |
| `TICK_INTERVAL_MS` | Simulator cadence                         | `1000`                              |
| `ZMQ_DIR`          | Directory for IPC sockets                 | `/tmp/etf-trading`                  |
| `MD_PUB_ADDR`      | Market data PUB socket name               | `md_pub.sock`                       |
| `PRICING_PUB_ADDR` | Pricing PUB socket name                   | `pricing_pub.sock`                  |
| `PCF_REQREP_ADDR`  | PCF service REP socket name               | `pcf_reqrep.sock`                   |
| `CALC_REQREP_ADDR` | (optional) external calc REQ/REP endpoint | empty                                |
| `WS_HOST`          | WebSocket gateway host                    | `localhost`                         |
| `WS_PORT`          | WebSocket gateway port                    | `9080`                              |

> The backend converts `*_ADDR` into full **IPC** paths under `ZMQ_DIR`. To force **TCP**, set `MD_PUB_ADDR=tcp://127.0.0.1:6001` (and similarly for others).

---

## Dev tips

- **Probing the WebSocket** (no browser):

  ```bash
  python -m backend.scripts.ws_probe
  ```

- **Formatting & linting**:

  ```bash
  black backend
  ruff check backend
  mypy backend
  ```

- **Tests** (placeholder):

  ```bash
  pytest -q
  ```

- **Troubleshooting**:
  - Ensure all four simulators and the gateway are running.
  - If you see “connection refused” in the frontend, verify `WS_HOST/WS_PORT` and try `?ws=ws://localhost:9080/stream` in the page URL.
  - Delete stale socket files in `ZMQ_DIR` if a service crashes.

---

## License

MIT (or as provided by the repository owner).
