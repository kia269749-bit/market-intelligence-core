"""Capital-aware exchange economics for research signals."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ExchangeProfile:
    name: str
    taker_fee_bps: float
    maker_fee_bps: float
    spread_bps: float = 5.0
    slippage_bps: float = 8.0

PROFILES = {
    "hyperliquid_perps": ExchangeProfile("hyperliquid_perps", 4.5, 1.5),
    "binance_spot_regular": ExchangeProfile("binance_spot_regular", 10.0, 10.0),
}

@dataclass(frozen=True)
class CapitalTarget:
    approved: bool
    capital_usd: float
    min_profit_usd: float
    expected_move_pct: float
    round_trip_cost_pct: float
    net_move_pct: float
    modeled_profit_usd: float
    required_move_pct: float
    reason: str

def evaluate_capital_target(expected_move_pct, capital_usd=100.0,
                            min_profit_usd=10.0,
                            exchange="hyperliquid_perps",
                            order_type="taker",
                            spread_bps=None, slippage_bps=None):
    if capital_usd <= 0 or min_profit_usd <= 0:
        return CapitalTarget(False, capital_usd, min_profit_usd, expected_move_pct, 0, 0, 0, 0, "invalid_policy")
    p = PROFILES[exchange]
    fee = p.maker_fee_bps if str(order_type).lower() == "maker" else p.taker_fee_bps
    spread = p.spread_bps if spread_bps is None else float(spread_bps)
    slip = p.slippage_bps if slippage_bps is None else float(slippage_bps)
    cost = 2.0 * (fee + spread + slip) / 100.0
    net = float(expected_move_pct) - cost
    required = min_profit_usd / capital_usd * 100.0 + cost
    profit = capital_usd * net / 100.0
    ok = net >= min_profit_usd / capital_usd * 100.0
    return CapitalTarget(ok, capital_usd, min_profit_usd, float(expected_move_pct),
                         round(cost, 4), round(net, 4), round(profit, 2),
                         round(required, 4),
                         "usd10_net_target_passed" if ok else "expected_move_below_usd10_after_costs")
