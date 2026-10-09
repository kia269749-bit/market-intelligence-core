"""Lightweight multi-horizon price-path forecasting and opportunity control.

Research-only. Uses only information available at the forecast timestamp.
It estimates 5/10/20/50-bar scenarios from rolling regime, momentum,
flow, volatility and empirical forward-return analogues. It does not
place orders and must not be treated as a guarantee of future prices.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
from typing import Iterable, Sequence

from .models import MarketBar


HORIZONS = (5, 10, 20, 50)


@dataclass(frozen=True)
class HorizonForecast:
    horizon: int
    direction: str
    confidence: float
    expected_return_pct: float
    lower_return_pct: float
    upper_return_pct: float
    favorable_target_pct: float
    adverse_move_pct: float
    target_hit_probability: float
    analog_samples: int


@dataclass(frozen=True)
class PathForecast:
    symbol: str
    ts: int
    price: float
    horizons: tuple[HorizonForecast, ...]
    regime: str
    trend_score: float
    data_samples: int
    research_only: bool = True
    live_orders: bool = False


def _ret(a: float, b: float) -> float:
    return math.log(a / b) if a > 0 and b > 0 else 0.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _flow(b: MarketBar) -> float:
    buy = float(b.buy_volume or 0.0)
    sell = float(b.sell_volume or 0.0)
    den = buy + sell
    return (buy - sell) / den if den else 0.0


def _trend_score(bars: Sequence[MarketBar], window: int = 20) -> float:
    if len(bars) < window + 1:
        return 0.0
    rs = [_ret(bars[i].price, bars[i - 1].price) for i in range(len(bars) - window, len(bars))]
    vol = statistics.pstdev(rs) or 1e-8
    return _clamp(sum(rs) / (vol * math.sqrt(window)), -3.0, 3.0)


def _regime(bars: Sequence[MarketBar]) -> str:
    if len(bars) < 25:
        return "UNKNOWN"
    score = _trend_score(bars, 20)
    rs = [_ret(bars[i].price, bars[i - 1].price) for i in range(len(bars) - 20, len(bars))]
    vol = statistics.pstdev(rs) or 0.0
    if abs(score) >= 1.25 and vol > 0:
        return "TREND"
    if vol > statistics.pstdev(
        [_ret(bars[i].price, bars[i - 1].price) for i in range(1, len(bars))]
    ) * 1.35:
        return "HIGH_VOL"
    return "RANGE"


def _analog_returns(
    bars: Sequence[MarketBar],
    horizon: int,
    window: int = 20,
    lookback: int = 500,
    min_samples: int = 40,
) -> list[float]:
    """Collect strictly historical forward returns.

    For index i, the feature is built from bars ending at i and the label
    starts at i+1. Thus the current forecast never consumes future data.
    """
    n = len(bars)
    if n <= window + horizon:
        return []
    current_score = _trend_score(bars, window)
    current_flow = sum(_flow(bars[i]) for i in range(n - window, n)) / window
    start = max(window, n - lookback - horizon)
    values: list[float] = []
    for i in range(start, n - horizon):
        local = bars[: i + 1]
        score = _trend_score(local, window)
        flow = sum(_flow(local[k]) for k in range(i - window + 1, i + 1)) / window
        if abs(score - current_score) <= 0.75 and abs(flow - current_flow) <= 0.30:
            values.append(_ret(bars[i + horizon].price, bars[i].price) * 100.0)
    if len(values) >= min_samples:
        return values
    # Deterministic fallback: all strictly historical observations.
    return [
        _ret(bars[i + horizon].price, bars[i].price) * 100.0
        for i in range(start, n - horizon)
    ]


def _forecast_one(
    bars: Sequence[MarketBar],
    horizon: int,
    target_move_pct: float,
) -> HorizonForecast:
    rs = [_ret(bars[i].price, bars[i - 1].price) for i in range(max(1, len(bars) - 20), len(bars))]
    vol_pct = (statistics.pstdev(rs) or 1e-8) * math.sqrt(horizon) * 100.0
    trend = _trend_score(bars, 20)
    vals = _analog_returns(bars, horizon)
    if not vals:
        vals = [trend * vol_pct / max(1.0, math.sqrt(horizon))]

    mean = statistics.fmean(vals)
    med = statistics.median(vals)
    # Blend empirical central tendency with current regime direction.
    regime_component = _clamp(trend / 3.0, -1.0, 1.0) * vol_pct * 0.35
    expected = 0.65 * med + 0.35 * regime_component
    spread = statistics.pstdev(vals) if len(vals) > 1 else vol_pct
    lower = expected - 1.0 * spread
    upper = expected + 1.0 * spread

    direction = "UP" if expected > 0 else "DOWN" if expected < 0 else "FLAT"
    favorable = abs(expected)
    adverse = max(0.0, -lower if direction == "UP" else upper if direction == "DOWN" else spread)
    if direction == "UP":
        directional_hits = sum(x > 0 for x in vals)
        target_hits = sum(x >= target_move_pct for x in vals)
    elif direction == "DOWN":
        directional_hits = sum(x < 0 for x in vals)
        target_hits = sum(x <= -target_move_pct for x in vals)
    else:
        directional_hits = sum(abs(x) <= 0.15 for x in vals)
        target_hits = 0
    # Smoothed historical analogue frequencies replace the old trend-based
    # confidence formula, which could report high confidence without wins.
    confidence = (directional_hits + 2.0) / (len(vals) + 4.0) if vals else 0.5
    hit_prob = (target_hits + 1.0) / (len(vals) + 2.0) if vals and direction != "FLAT" else 0.0

    return HorizonForecast(
        horizon=horizon,
        direction=direction,
        confidence=round(_clamp(confidence, 0.0, 1.0), 4),
        expected_return_pct=round(expected, 4),
        lower_return_pct=round(lower, 4),
        upper_return_pct=round(upper, 4),
        favorable_target_pct=round(favorable, 4),
        adverse_move_pct=round(adverse, 4),
        target_hit_probability=round(_clamp(hit_prob, 0.0, 1.0), 4),
        analog_samples=len(vals),
    )


def forecast_path(
    bars: Sequence[MarketBar],
    horizons: Iterable[int] = HORIZONS,
    min_history: int = 140,
    target_move_pct: float = 1.15,
) -> PathForecast | None:
    """Forecast multiple future horizons from the latest completed bar."""
    if len(bars) < min_history:
        return None
    hs = tuple(sorted({int(h) for h in horizons if int(h) > 0}))
    if not hs:
        return None
    forecasts = tuple(_forecast_one(bars, h, target_move_pct) for h in hs)
    return PathForecast(
        symbol=bars[-1].symbol,
        ts=int(bars[-1].ts),
        price=float(bars[-1].price),
        horizons=forecasts,
        regime=_regime(bars),
        trend_score=round(_trend_score(bars, 20), 4),
        data_samples=len(bars),
    )


def path_to_economic_opportunity(
    path: PathForecast,
    capital_usd: float = 500.0,
    round_trip_cost_pct: float = 0.35,
    min_profit_usd: float = 4.0,
    preferred_profit_usd: float = 10.0,
) -> dict:
    """Translate forecast paths into economic opportunity, without forcing a trade."""
    min_move = min_profit_usd / capital_usd * 100.0 + round_trip_cost_pct
    preferred_move = preferred_profit_usd / capital_usd * 100.0 + round_trip_cost_pct

    rows = []
    for f in path.horizons:
        expected_net = abs(f.expected_return_pct) - round_trip_cost_pct
        modeled_profit = capital_usd * expected_net / 100.0
        if f.target_hit_probability >= 0.55 and abs(f.expected_return_pct) >= preferred_move:
            tier = "STRONG"
        elif f.target_hit_probability >= 0.45 and abs(f.expected_return_pct) >= min_move:
            tier = "VIABLE"
        elif f.target_hit_probability >= 0.35 and abs(f.expected_return_pct) >= min_move:
            tier = "WATCH"
        else:
            tier = "REJECT"
        rows.append({
            "horizon": f.horizon,
            "direction": f.direction,
            "confidence": f.confidence,
            "expected_return_pct": f.expected_return_pct,
            "expected_move_pct": abs(f.expected_return_pct),
            "target_hit_probability": f.target_hit_probability,
            "analog_samples": f.analog_samples,
            "adverse_move_pct": f.adverse_move_pct,
            "risk_reward_ratio": round(abs(f.expected_return_pct) / max(f.adverse_move_pct, 1e-6), 4),
            "modeled_net_profit_usd": round(modeled_profit, 2),
            "tier": tier,
            "tier_reason": {
                "STRONG": "target_probability_and_preferred_net_profit_pass",
                "VIABLE": "target_probability_and_minimum_net_profit_pass",
                "WATCH": "marginal_target_probability",
                "REJECT": "insufficient_empirical_target_probability_or_net_move",
            }[tier],
        })

    # Prefer a genuinely viable horizon over a larger but statistically weak
    # expected move. Previously a rejected horizon could hide a viable one.
    tier_rank = {"STRONG": 3, "VIABLE": 2, "WATCH": 1, "REJECT": 0}
    best = max(
        rows,
        key=lambda r: (tier_rank[r["tier"]], r["target_hit_probability"],
                       r["risk_reward_ratio"], r["modeled_net_profit_usd"]),
        default=None,
    )
    return {
        "best": best,
        "horizons": rows,
        "minimum_required_move_pct": round(min_move, 4),
        "preferred_required_move_pct": round(preferred_move, 4),
        "capital_usd": capital_usd,
        "round_trip_cost_pct": round_trip_cost_pct,
        "research_only": True,
        "live_orders": False,
    }
