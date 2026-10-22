"""Single source of truth for research market, venue, and execution assumptions.

This module is deliberately read-only with respect to exchange accounts. It does not
place orders or retrieve private account data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config" / "default.json"
MARKETS_CONFIG_PATH = ROOT / "config" / "markets.json"


@dataclass(frozen=True)
class CentralSettings:
    exchange: str
    market: str
    product_group: str
    symbols: tuple[str, ...]
    poll_seconds: int
    taker_fee_bps: float
    maker_fee_bps: float
    fee_source: str
    fee_account_verified: bool
    spread_bps: float
    slippage_bps: float
    impact_bps: float
    latency_bars: int
    research_only: bool
    live_orders: bool


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"required central config missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in central config: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"central config must be a JSON object: {path}")
    return value


def load_settings() -> CentralSettings:
    defaults = _read_json(DEFAULT_CONFIG_PATH)
    markets = _read_json(MARKETS_CONFIG_PATH)
    fees = defaults.get("fees", {})
    costs = defaults.get("costs", {})
    if not isinstance(fees, dict) or not isinstance(costs, dict):
        raise RuntimeError("fees and costs config sections must be objects")

    exchange = str(markets.get("primary_exchange", markets.get("exchange", "lbank"))).lower()
    market = str(markets.get("market", "futures")).lower()
    product_group = str(markets.get("product_group", "SwapU"))
    if exchange != "lbank":
        raise RuntimeError(f"unsupported primary exchange in central config: {exchange}")
    if market != "futures":
        raise RuntimeError(f"unsupported market type in central config: {market}")
    if not product_group:
        raise RuntimeError("product_group must not be empty")

    symbols = markets.get("symbols", [])
    if not isinstance(symbols, list) or not symbols:
        raise RuntimeError("central config must define a non-empty symbols list")
    normalized_symbols = tuple(str(s).upper().replace("/", "").replace("-", "") for s in symbols)
    if any(not s for s in normalized_symbols):
        raise RuntimeError("symbols must not contain empty values")

    settings = CentralSettings(
        exchange=exchange,
        market=market,
        product_group=product_group,
        symbols=normalized_symbols,
        poll_seconds=int(markets.get("poll_seconds", 20)),
        taker_fee_bps=float(fees.get("taker_bps", costs.get("fee_bps", 6.0))),
        maker_fee_bps=float(fees.get("maker_bps", 2.0)),
        fee_source=str(fees.get("source", "lbank_published_default")),
        fee_account_verified=bool(fees.get("account_specific_verified", False)),
        spread_bps=float(costs.get("spread_bps", 2.0)),
        slippage_bps=float(costs.get("slippage_bps", 3.0)),
        impact_bps=float(costs.get("impact_bps", 1.0)),
        latency_bars=int(costs.get("latency_bars", 1)),
        research_only=bool(markets.get("research_only", True)),
        live_orders=bool(markets.get("live_orders", False)),
    )
    if settings.poll_seconds < 5:
        raise RuntimeError("poll_seconds must be at least 5")
    if settings.research_only is not True or settings.live_orders is not False:
        raise RuntimeError("unsafe configuration: research_only must be true and live_orders false")
    for name in ("taker_fee_bps", "maker_fee_bps", "spread_bps", "slippage_bps", "impact_bps"):
        if getattr(settings, name) < 0:
            raise RuntimeError(f"{name} must be non-negative")
    if settings.latency_bars < 0:
        raise RuntimeError("latency_bars must be non-negative")
    return settings
