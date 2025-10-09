from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import List, Dict

from backend.core.schemas import Exchange, Security

DATA_PATH = Path(__file__).resolve().parents[1] / 'data' / 'universe.json'


@dataclass
class Universe:
    securities: List[Security]
    exchanges: Dict[str, Exchange]


def _default_universe() -> Universe:
    """Hard-coded minimal universe for MVP0 (5 ETFs + a few large caps)."""
    exchanges = [
        Exchange(id="XNAS", name="Nasdaq", timezone="America/New_York", open_time="09:30", close_time="16:00"),
        Exchange(id="XNYS", name="NYSE", timezone="America/New_York", open_time="09:30", close_time="16:00"),
        Exchange(id="XPAR", name="Euronext Paris", timezone="Europe/Paris", open_time="09:00", close_time="17:30"),
        Exchange(id="XETR", name="Xetra", timezone="Europe/Berlin", open_time="09:00", close_time="17:30"),
        Exchange(id="XSHG", name="Shanghai SE", timezone="Asia/Shanghai", open_time="09:30", close_time="15:00"),
    ]
    ex_map = {e.id: e for e in exchanges}

    securities = [
        # ETFs (placeholders for dev)
        Security(
            id="ETF_SP500",
            isin=None,
            ticker="SPYx",
            name="S&P 500 Tracker (sim)",
            exchange_id="XNYS",
            currency="USD",
            type="ETF",
        ),
        Security(
            id="ETF_CSI1000",
            isin=None,
            ticker="CSI1k",
            name="CSI 1000 Tracker (sim)",
            exchange_id="XSHG",
            currency="CNY",
            type="ETF",
        ),
        Security(
            id="ETF_CAC40",
            isin=None,
            ticker="CACx",
            name="CAC 40 Tracker (sim)",
            exchange_id="XPAR",
            currency="EUR",
            type="ETF",
        ),
        Security(
            id="ETF_MSCI_W",
            isin=None,
            ticker="MSCIw",
            name="MSCI World Tracker (sim)",
            exchange_id="XETR",
            currency="EUR",
            type="ETF",
        ),
        Security(
            id="ETF_STOXX600",
            isin=None,
            ticker="STOXX",
            name="EURO STOXX 600 Tracker (sim)",
            exchange_id="XETR",
            currency="EUR",
            type="ETF",
        ),
        # A few large caps to have moving constituents
        Security(id="AAPL", isin="US0378331005", ticker="AAPL", name="Apple Inc", exchange_id="XNAS", currency="USD"),
        Security(id="MSFT", isin="US5949181045", ticker="MSFT", name="Microsoft", exchange_id="XNAS", currency="USD"),
        Security(id="AIR", isin="NL0000235190", ticker="AIR", name="Airbus SE", exchange_id="XPAR", currency="EUR"),
        Security(id="OR", isin="FR0000120321", ticker="OR", name="L'Oréal SA", exchange_id="XPAR", currency="EUR"),
        Security(id="SIE", isin="DE0007236101", ticker="SIE", name="Siemens AG", exchange_id="XETR", currency="EUR"),
    ]
    return Universe(securities=securities, exchanges=ex_map)


def _load_from_json(path: Path) -> Universe:
    data = json.loads(path.read_text())
    exchanges = {e['id']: Exchange(**e) for e in data['exchanges']}
    securities = [Security(**s) for s in data['securities']]
    return Universe(securities=securities, exchanges=exchanges)


def _save_to_json(path: Path, uni: Universe) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'exchanges': [e.model_dump() for e in uni.exchanges.values()],
        'securities': [s.model_dump() for s in uni.securities],
    }
    path.write_text(json.dumps(payload, indent=2))


def load_universe() -> Universe:
    if DATA_PATH.exists():
        return _load_from_json(DATA_PATH)
    uni = _default_universe()
    try:
        _save_to_json(DATA_PATH, uni)
    except:
        pass
    return uni
