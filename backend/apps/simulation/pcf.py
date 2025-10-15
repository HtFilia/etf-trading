from __future__ import annotations
from typing import Optional, Dict
import random
import asyncio
from backend.core.config import get_config
from backend.core.logging import get_logger
from backend.core.zmq_bus import RepSocket, shutdown_sockets
from backend.core.utils.services import run_service
from backend.core.universe import load_universe
from backend.core.schemas import ETFPCF, Basket, BasketLine, ETFCosts

CFG = get_config()
log = get_logger(__name__)

_rep: Optional[RepSocket] = None

# ----------------------------------------------------------------------
# Helper: generate PCFs for the ETFs in the universe
# ----------------------------------------------------------------------

def generate_etf_pcfs() -> Dict[str, ETFPCF]:
    universe = load_universe()
    equities = [s for s in universe.securities if s.type == "EQUITY"]
    etfs = [s for s in universe.securities if s.type == "ETF"]

    fx_currencies = ["USD", "EUR", "GBP"]

    pcfs: Dict[str, ETFPCF] = {}

    for etf in etfs:
        # Pick a few random equities for the ETF basket
        basket_equities = random.sample(equities, k=min(6, len(equities)))

        composition: list[BasketLine] = []
        total_weight = 0.0

        # Add equity components with random quantities
        for eq in basket_equities:
            qty = round(random.uniform(1, 10), 2)
            composition.append(
                BasketLine(
                    security_id=eq.id,
                    quantity=qty,
                    currency=eq.currency,
                )
            )
            total_weight += qty

        # Add cash lines in 1–2 currencies
        for cash_ccy in random.sample(fx_currencies, k=random.randint(1, 2)):
            cash_amount = round(random.uniform(20, 100), 2)
            composition.append(
                BasketLine(
                    security_id=cash_ccy,
                    quantity=cash_amount,
                    currency=cash_ccy,
                )
            )

        # Build the tracking basket
        basket = Basket(
            version=1,
            divisor=100.0,
            composition=composition,
        )

        # Build the full PCF
        pcf = ETFPCF(
            etf_id=etf.id,
            currency=etf.currency,
            baskets={"tracking": basket},
            costs=ETFCosts(
                flat_create=100.0,
                flat_redeem=100.0,
                per_line_bps=0.0,
                per_venue_bps={"NYSE": 0.2},
            ),
            stamp_duties={
                "UK": {"buy": 50.0, "sell": 0.0},
                "FR": {"buy": 40.0, "sell": 0.0},
            },
        )

        pcfs[etf.id] = pcf

    return pcfs


# ----------------------------------------------------------------------
# PCF Simulator State
# ----------------------------------------------------------------------

_state: Dict[str, ETFPCF] = generate_etf_pcfs()

# ----------------------------------------------------------------------
# Async Server
# ----------------------------------------------------------------------

async def init() -> None:
    global _rep
    _rep = await RepSocket.bind(CFG.pcf_ipc)
    log.info("pcf_sim bound", extra={"endpoint": CFG.pcf_ipc})


async def server() -> None:
    assert _rep is not None
    while True:
        req = await _rep.recv()
        op = req.get("op")
        try:
            if op == "list_etfs":
                await _rep.send({"ok": True, "etfs": list(_state.keys())})

            elif op == "get_pcf":
                etf_id = req["etf_id"]
                pcf = _state.get(etf_id)
                await _rep.send(
                    {"ok": True, "pcf": pcf.model_dump(mode="json") if pcf else None}
                )

            else:
                await _rep.send({"ok": False, "err": f"unknown_op:{op}"})

        except Exception as e:
            log.exception("pcf_sim error %s", e)
            await _rep.send({"ok": False, "err": str(e)})


# ----------------------------------------------------------------------
# Shutdown & Runner
# ----------------------------------------------------------------------

async def shutdown() -> None:
    await shutdown_sockets(_rep)
    log.info("pcf_sim shutdown complete")


async def run():
    await run_service(
        name="pcf_sim",
        init=init,
        main=server,
        on_shutdown=[shutdown],
    )


if __name__ == "__main__":
    asyncio.run(run())
