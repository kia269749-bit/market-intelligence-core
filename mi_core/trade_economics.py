"""Capital-aware exchange economics for research signals."""
from dataclasses import dataclass
import math
from .costs import get_round_trip_cost_pct

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
                            exchange="hyperliquid_perps", order_type="taker",
                            spread_bps=None, slippage_bps=None,
                            cost_policy="base"):
    p = PROFILES.get(exchange)
    if p is None:
        return CapitalTarget(False, "REJECT", capital_usd, min_profit_usd,
                             preferred_profit_usd, expected_move_pct,
                             0.0, 0.0, 0.0, 0.0, 0.0, "invalid_policy")

    try:
        expected = float(expected_move_pct)
        capital = float(capital_usd)
        minimum = float(min_profit_usd)
        preferred = float(preferred_profit_usd)
        spread = p.spread_bps if spread_bps is None else float(spread_bps)
        slip = p.slippage_bps if slippage_bps is None else float(slippage_bps)
    except (TypeError, ValueError, OverflowError):
        return CapitalTarget(False, "REJECT", capital_usd, min_profit_usd,
                             preferred_profit_usd, expected_move_pct,
                             0.0, 0.0, 0.0, 0.0, 0.0, "invalid_input")

    values = (expected, capital, minimum, preferred, spread, slip)
    if not all(math.isfinite(v) for v in values):
        return CapitalTarget(False, "REJECT", capital, minimum, preferred,
                             expected, 0.0, 0.0, 0.0, 0.0, 0.0,
                             "invalid_input")

    if spread < 0 or slip < 0:
        return CapitalTarget(False, "REJECT", capital, minimum, preferred,
                             expected, 0.0, 0.0, 0.0, 0.0, 0.0,
                             "invalid_input")

    if capital <= 0 or minimum <= 0 or preferred < minimum:
        return CapitalTarget(False, "REJECT", capital, minimum, preferred,
                             expected, 0.0, 0.0, 0.0, 0.0, 0.0,
                             "invalid_policy")

    try:
        cost = get_round_trip_cost_pct(cost_policy)
    except ValueError:
        return CapitalTarget(False, "REJECT", capital, minimum, preferred,
                             expected, 0.0, 0.0, 0.0, 0.0, 0.0,
                             "invalid_policy")
    # Explicit spread/slippage overrides adjust the central policy by
    # their difference from the profile defaults; they do not replace it.
    cost += 2.0 * ((spread - p.spread_bps) + (slip - p.slippage_bps)) / 100.0
    if str(order_type).lower() == "maker":
        cost -= 2.0 * (p.taker_fee_bps - p.maker_fee_bps) / 100.0
    if not math.isfinite(cost) or cost < 0:
        return CapitalTarget(False, "REJECT", capital, minimum, preferred,
                             expected, 0.0, 0.0, 0.0, 0.0, 0.0,
                             "invalid_input")
    net = expected - cost
    min_net_pct = minimum / capital * 100.0
    preferred_net_pct = preferred / capital * 100.0
    required = min_net_pct + cost
    preferred_required = preferred_net_pct + cost
    profit = capital * net / 100.0

    if net >= preferred_net_pct:
        tier, approved, reason = "STRONG", True, "preferred_usd10_target_passed"
    elif net >= min_net_pct:
        tier, approved, reason = "WATCH", True, "minimum_usd4_target_passed"
    else:
        tier, approved, reason = "REJECT", False, "expected_move_below_usd4_after_costs"

    return CapitalTarget(approved, tier, capital, minimum, preferred, expected,
                         round(cost, 4), round(net, 4), round(profit, 2),
                         round(required, 4), round(preferred_required, 4), reason)
