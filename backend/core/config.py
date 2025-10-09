from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    _ENV_LOADED = load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / '.env')
except:
    _ENV_LOADED = False

def _ensure_ipc(addr: Optional[str], default_name: str) -> str:
    if not addr:
        base = os.environ.get('ZMQ_DIR', '/tmp/etf-trading')
        return f'ipc://{Path(base) / default_name}'
    if addr.startswith(('ipc://', 'tcp://')):
        return addr
    if addr.startswith('/'):
        return f'ipc://{addr}'
    base = os.environ.get('ZMQ_DIR', '/tmp/etf-trading')
    return f'ipc://{Path(base) / addr}'

@dataclass(frozen=True)
class AppConfig:
    env_loaded: bool
    dev_mode: bool
    tick_interval_ms: float
    
    zmq_dir: str
    md_pub_addr: str
    pcf_reqrep_addr: str
    pricing_pub_addr: str
    calc_reqrep_addr: str
    
    ws_host: str
    ws_port: int
    
    @property
    def tick_interval(self) -> float:
        return self.tick_interval_ms / 1000.0
    
    @property
    def md_pub_ipc(self) -> str:
        return _ensure_ipc(self.md_pub_addr, 'md_pub.sock')
    
    @property
    def pcf_reqrep_ipc(self) -> str:
        return _ensure_ipc(self.pcf_reqrep_addr, 'pcf_reqrep.sock')
    
    @property
    def pricing_pub_ipc(self) -> str:
        return _ensure_ipc(self.pricing_pub_addr, 'pricing_pub.sock')
    
    @property
    def calc_reqrep_ipc(self) -> str:
        return _ensure_ipc(self.calc_reqrep_addr, 'calc_reqrep.sock') if self.calc_reqrep_addr else ''

@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    def as_bool(s: Optional[str], default: bool) -> bool:
        if s is None:
            return default
        return s.strip().lower() in ('1', 'true', 'yes', 'on')
    def as_float(s: Optional[str], default: float) -> float:
        try:
            return float(s) if s is not None else default
        except ValueError:
            return default
    def as_int(s: Optional[str], default: int) -> int:
        try:
            return int(s) if s is not None else default
        except ValueError:
            return default
    
    return AppConfig(
        env_loaded=_ENV_LOADED,
        dev_mode=as_bool(os.environ.get('DEV_MODE'), True),
        tick_interval_ms=as_float(os.environ.get('TICK_INTERVAL_MS'), 1000.0),
        zmq_dir=os.environ.get('ZMQ_DIR', '/tmp/etf-trading'),
        md_pub_addr=os.environ.get('MD_PUB_ADDR', ''),
        pcf_reqrep_addr=os.environ.get('PCF_REQREP_ADDR', ''),
        pricing_pub_addr=os.environ.get('PRICING_PUB_ADDR', ''),
        calc_reqrep_addr=os.environ.get('CALC_REQREP_ADDR', ''),
        ws_host=os.environ.get('WS_HOST', 'localhost'),
        ws_port=as_int(os.environ.get('WS_PORT'), 9080),
    )