# Backend (Python / Starlette / ZeroMQ)

The backend is a set of small async services that publish and consume messages via **ZeroMQ**, expose a **WebSocket** for browsers, and define strongly‑typed **Pydantic** schemas.

## Services

- **`apps/simulation/market_data.py`** – emits `prices.tick` for a small hard‑coded universe (see `core/universe.py`).  
- **`apps/simulation/fx.py`** – emits `fx.spot` and a light forward curve.  
- **`apps/simulation/pricing.py`** – listens to `prices.*` and `fx.*`, computes toy **iNAV**/bands, and publishes `inav.*`.  
- **`apps/simulation/pcf.py`** – toy **PCF** server (REQ/REP) for basket details/costs.  
- **`apps/gateway_ws/main.py`** – **Starlette + Uvicorn** app that subscribes to PUB sockets and forwards JSON over **WebSocket** at `/stream`.

### Topics

- Market data: `prices.tick` (`PriceTick`), FX: `fx.spot`, Pricing: `inav.tick`.  
- All messages are JSON‑serializable; numpy scalars/arrays are converted to native types by `core/zmq_bus.py`.

## Core modules

- `core/config.py` – loads `.env` with `python-dotenv`; provides resolved addresses for IPC/TCP.  
- `core/zmq_bus.py` – `PubSocket`, `SubSocket`, `ReqSocket`, `RepSocket` wrappers (asyncio + msgpack/json).  
- `core/schemas.py` – `Exchange`, `Security`, `PriceTick`, etc. (Pydantic v2).  
- `core/universe.py` – minimal instrument universe and exchanges.  
- `core/timecal/` – trading hours + `is_open()` helpers.  
- `core/logging.py` – structured logging with optional file handlers.  
- `core/utils/services.py` – `run_service()` helper with signal handling and graceful shutdown.

## Run locally

1) **Environment & deps**  

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

2) **Start services (each in its own terminal or background)**  

```bash
# Market data
python -m backend.apps.simulation.market_data

# FX
python -m backend.apps.simulation.fx

# Pricing
python -m backend.apps.simulation.pricing

# PCF
python -m backend.apps.simulation.pcf

# WebSocket gateway
python -m backend.apps.gateway_ws.main
```

The gateway listens on `ws://{WS_HOST}:{WS_PORT}/stream` (defaults to `ws://localhost:9080/stream`).

## Configuration

See the repo‑level README for the complete table. Addresses default to **IPC sockets** under `ZMQ_DIR`; override with explicit **TCP** URIs on Windows or for cross‑host setups.

## Minimal API

- **WebSocket**: `/stream`  
  Messages are NDJSON‑style JSON frames with shape:

  ```json
  { "type": "prices.tick", "ts": 1731234567890, "payload": { /* schema */ } }
  ```

## Testing / tools

- `backend/scripts/ws_probe.py` – quick WebSocket sanity check.
- Run `black`, `ruff`, `mypy` over `backend/`.
- `pytest` (test skeletons to be extended).

## Notes

This code is intentionally simple; performance, durability, and risk controls are out of scope.
