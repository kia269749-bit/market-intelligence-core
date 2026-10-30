"""Capital-aware research economics using the central cost convention."""
from dataclasses import dataclass
import math

from .costs import get_round_trip_cost_pct


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


def evaluate_capital_target(
    expected_move_pct, capital_usd=500.0, min_profit_usd=4.0,
    preferred_profit_usd=10.0, *, cost_policy="base",
    round_trip_cost_pct=None, exchange=None, order_type=None,
):
    """Evaluate a forecast move; research policy and explicit override are exclusive.

    exchange/order_type are accepted only for legacy call compatibility and do
    not select venue fee schedules. Use explicit round_trip_cost_pct overrides
    or the central base/strict research policy instead.
    """
    values = (expected_move_pct, capital_usd, min_profit_usd, preferred_profit_usd)
    try:
        nums = [float(x) if not isinstance(x, bool) else math.nan for x in values]
    except (TypeError, ValueError, OverflowError):
        nums = [math.nan] * 4
    move, capital, minimum, preferred = nums
    if (not all(math.isfinite(x) for x in nums) or capital <= 0 or
            minimum <= 0 or preferred < minimum):
        raise ValueError("invalid capital target inputs")
    if round_trip_cost_pct is None:
        cost = get_round_trip_cost_pct(cost_policy)
    else:
        if isinstance(round_trip_cost_pct, bool):
            raise ValueError("round_trip_cost_pct must be finite and non-negative")
        try:
            cost = float(round_trip_cost_pct)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("round_trip_cost_pct must be finite and non-negative") from None
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("round_trip_cost_pct must be finite and non-negative")
    net = move - cost
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
    return CapitalTarget(approved, tier, capital, minimum, preferred, move, round(cost, 4),
                         round(net, 4), round(profit, 2), round(required, 4),
                         round(preferred_required, 4), reason)
