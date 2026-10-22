"""Capital-aware economics using the centralized LBank futures settings by default."""
from dataclasses import dataclass

from .central_config import load_settings


@dataclass(frozen=True)
class ExchangeProfile:
    name: str
    taker_fee_bps: float
    maker_fee_bps: float
    spread_bps: float = 5.0
    slippage_bps: float = 8.0


# Legacy profiles remain available only when a caller explicitly names them.
# New/default project paths use the centralized LBank futures configuration.
PROFILES = {
    "hyperliquid_perps": ExchangeProfile("hyperliquid_perps", 4.5, 1.5),
    "binance_spot_regular": ExchangeProfile("binance_spot_regular", 10.0, 10.0),
}


@dataclass(frozen=True)
class CapitalTarget:
    approved: bool
    tier: str
    capital_usd: float
    min_profit_usd: float
    preferred_profit_usd: float
    expected_move_pct: float
    round_trip_cost_pct: float
    net_move_pct: float
    modeled_profit_usd: float
    required_move_pct: float
    preferred_required_move_pct: float
    reason: str


def evaluate_capital_target(expected_move_pct, capital_usd=500.0,
                            min_profit_usd=4.0, preferred_profit_usd=10.0,
                            exchange=None, order_type="taker",
                            spread_bps=None, slippage_bps=None,
                            impact_bps=None):
    if capital_usd <= 0 or min_profit_usd <= 0 or preferred_profit_usd < min_profit_usd:
        return CapitalTarget(False, "REJECT", capital_usd, min_profit_usd, preferred_profit_usd,
                             expected_move_pct, 0, 0, 0, 0, 0, "invalid_policy")

    settings = load_settings()
    if exchange is None or str(exchange).lower() in ("lbank", "lbank_futures"):
        fee = settings.maker_fee_bps if str(order_type).lower() == "maker" else settings.taker_fee_bps
        spread_default = settings.spread_bps
        slip_default = settings.slippage_bps
        impact_default = settings.impact_bps
    else:
        profile = PROFILES.get(str(exchange).lower())
        if profile is None:
            raise ValueError(f"unsupported exchange profile: {exchange}")
        fee = profile.maker_fee_bps if str(order_type).lower() == "maker" else profile.taker_fee_bps
        spread_default = profile.spread_bps
        slip_default = profile.slippage_bps
        impact_default = 0.0

    spread = spread_default if spread_bps is None else float(spread_bps)
    slip = slip_default if slippage_bps is None else float(slippage_bps)
    impact = impact_default if impact_bps is None else float(impact_bps)
    cost = 2.0 * (fee + spread + slip + impact) / 100.0
    net = float(expected_move_pct) - cost
    min_net_pct = min_profit_usd / capital_usd * 100.0
    preferred_net_pct = preferred_profit_usd / capital_usd * 100.0
    required = min_net_pct + cost
    preferred_required = preferred_net_pct + cost
    profit = capital_usd * net / 100.0
    if net >= preferred_net_pct:
        tier, approved, reason = "STRONG", True, "preferred_usd10_target_passed"
    elif net >= min_net_pct:
        tier, approved, reason = "WATCH", True, "minimum_usd4_target_passed"
    else:
        tier, approved, reason = "REJECT", False, "expected_move_below_usd4_after_costs"
    return CapitalTarget(approved, tier, capital_usd, min_profit_usd, preferred_profit_usd,
                         float(expected_move_pct), round(cost, 4), round(net, 4),
                         round(profit, 2), round(required, 4), round(preferred_required, 4), reason)
