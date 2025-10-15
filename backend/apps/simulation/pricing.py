from __future__ import annotations
import asyncio
from typing import Optional, Dict, Any
from backend.core.config import get_config
from backend.core.zmq_bus import SubSocket, PubSocket, ReqSocket, shutdown_sockets
from backend.core.utils.services import run_service
from backend.core.logging import get_logger
from backend.core.schemas import ETFPCF

CFG = get_config()
log = get_logger(__name__)

_sub_md: Optional[SubSocket] = None
_sub_fx: Optional[SubSocket] = None
_pub: Optional[PubSocket] = None
_pcf: Optional[ReqSocket] = None

_state: Dict[str, Any] = {
    "ticks": {},     # security_id -> last PriceTick
    "fx_spot": {},   # pair -> spot rate
    "fx_fwd": {},    # pair -> points
    "pcfs": {},      # etf_id -> ETFPCF
}

# ----------------------------------------------------------------------
# INIT
# ----------------------------------------------------------------------

async def init() -> None:
    global _sub_md, _sub_fx, _pub, _pcf
    _sub_md = await SubSocket.connect(CFG.md_ipc, topics=["prices."])
    _sub_fx = await SubSocket.connect(CFG.fx_ipc, topics=["fx."])
    _pub = await PubSocket.bind(CFG.pricing_ipc)
    _pcf = await ReqSocket.connect(CFG.pcf_ipc)

    log.info(
        "pricing connected",
        extra={
            "md_sub": CFG.md_ipc,
            "fx_sub": CFG.fx_ipc,
            "pricing_pub": CFG.pricing_ipc,
            "pcf_reqrep": CFG.pcf_ipc,
        },
    )

    await load_pcfs()


# ----------------------------------------------------------------------
# PCF loader (using send_and_recv)
# ----------------------------------------------------------------------

async def load_pcfs() -> None:
    assert _pcf is not None
    try:
        resp = await _pcf.send_and_recv({"op": "list_etfs"}, timeout=5.0)
    except Exception as e:
        log.error(f"Failed to list PCFs: {e}")
        return

    if not resp.get("ok"):
        log.error(f"PCF list request failed: {resp}")
        return

    for etf_id in resp.get("etfs", []):
        try:
            pcf_resp = await _pcf.send_and_recv({"op": "get_pcf", "etf_id": etf_id}, timeout=5.0)
            if pcf_resp.get("ok") and pcf_resp.get("pcf"):
                _state["pcfs"][etf_id] = ETFPCF.model_validate(pcf_resp["pcf"])
                log.info(f"Loaded PCF for {etf_id}")
            else:
                log.warning(f"No PCF data found for {etf_id}")
        except Exception as e:
            log.error(f"Error loading PCF for {etf_id}: {e}")


# ----------------------------------------------------------------------
# CONSUME MARKET AND FX DATA
# ----------------------------------------------------------------------

async def consume_bus() -> None:
    assert _sub_fx is not None
    assert _sub_md is not None

    async def handle_sub(sub: SubSocket):
        async for msg in sub:
            t = msg["type"]
            p = msg["payload"]

            if t == "prices.tick":
                _state["ticks"][p["security_id"]] = p
            elif t == "fx.spot":
                _state["fx_spot"][p["pair"].upper()] = p["spot"]
            elif t == "fx.forwards":
                _state["fx_fwd"][p["pair"].upper()] = p["points"]
    
    await asyncio.gather(
        handle_sub(_sub_fx),
        handle_sub(_sub_md),
    )


# ----------------------------------------------------------------------
# iNAV COMPUTATION LOOP
# ----------------------------------------------------------------------

async def publish_inav() -> None:
    assert _pub is not None
    tick_interval = CFG.tick_interval

    while True:
        for etf_id, pcf in _state["pcfs"].items():
            fair_value = compute_fair_value(pcf)
            if fair_value is None:
                continue

            band = fair_value * 0.001
            msg = {
                "etf_id": etf_id,
                "inav": fair_value,
                "band_low": round(fair_value - band, 4),
                "band_high": round(fair_value + band, 4),
            }
            await _pub.send("inav.tick", msg)

        await asyncio.sleep(tick_interval)


# ----------------------------------------------------------------------
# FAIR VALUE COMPUTATION
# ----------------------------------------------------------------------

def compute_fair_value(pcf: ETFPCF) -> Optional[float]:
    """Compute iNAV (ETF fair value) using live market data and FX rates."""
    ticks = _state["ticks"]
    fx_spot = _state["fx_spot"]

    fund_ccy = pcf.currency
    basket = pcf.baskets.get("tracking")
    if not basket or not basket.composition:
        return None

    total_value_fund_ccy = 0.0

    for line in basket.composition:
        ccy = line.currency
        fx_pair = f"{ccy}{fund_ccy}".upper()

        # FX conversion
        if ccy == fund_ccy:
            fx_rate = 1.0
        elif fx_pair in fx_spot:
            fx_rate = fx_spot[fx_pair]
        elif (inv := f"{fund_ccy}{ccy}".upper()) in fx_spot:
            fx_rate = 1.0 / fx_spot[inv]
        else:
            continue

        # Price
        if line.security_id in {"USD", "EUR", "GBP", "JPY"}:
            price = 1.0
        else:
            tick = ticks.get(line.security_id)
            if not tick:
                continue
            price = tick["mid"]

        total_value_fund_ccy += line.quantity * price * fx_rate

    if basket.divisor == 0:
        return None

    return round(total_value_fund_ccy / basket.divisor, 4)


# ----------------------------------------------------------------------
# SHUTDOWN
# ----------------------------------------------------------------------

async def shutdown() -> None:
    await shutdown_sockets(_sub_md, _sub_fx, _pub, _pcf)
    log.info("pricing shutdown complete")


# ----------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------

async def run():
    await run_service(
        name="pricing",
        init=init,
        main=publish_inav,
        background=[consume_bus],
        on_shutdown=[shutdown],
    )


if __name__ == "__main__":
    asyncio.run(run())
