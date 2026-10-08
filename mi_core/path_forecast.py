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
TARGET_LADDER_PCT = (0.20, 0.40, 0.60, 0.80, 1.00, 1.15)


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
    target_ladder_probability: tuple[tuple[float, float], ...] = ()


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



_FEATURE_NAMES = ("mom5","mom20","mom50","trend20","flow5","flow20","oi5","oi20","funding","vol20","volume_z20")
_MIN_ANALOGUES = 30
_MAX_ANALOGUES = 80
_LOOKBACK = 900
_EMBARGO_MULTIPLIER = 2
_WILSON_Z = 1.2815515655


def _num(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _oi_change(bars, lookback):
    if len(bars) <= lookback:
        return 0.0
    now, old = _num(bars[-1].oi), _num(bars[-1-lookback].oi)
    if now <= 0 or old <= 0:
        return 0.0
    return _clamp(math.log(now / old), -0.50, 0.50)


def _volume_z(bars, window=20):
    if len(bars) < window + 1:
        return 0.0
    recent = [_num(x.volume) for x in bars[-window:]]
    baseline = [_num(x.volume) for x in bars[-min(len(bars), window*5):-window]]
    if not baseline:
        return 0.0
    sd = statistics.pstdev(baseline) or 1e-12
    return _clamp((statistics.fmean(recent)-statistics.fmean(baseline))/sd, -5.0, 5.0)


def _feature_vector(bars):
    n = len(bars)
    if not n:
        return (0.0,) * len(_FEATURE_NAMES)
    p = [x.price for x in bars]
    def mom(k):
        return _ret(p[-1], p[-1-k])*100.0 if n > k else 0.0
    flow5 = statistics.fmean(_flow(x) for x in bars[-5:]) if n >= 5 else _flow(bars[-1])
    flow20 = statistics.fmean(_flow(x) for x in bars[-20:]) if n >= 20 else flow5
    rs20 = [_ret(p[i], p[i-1]) for i in range(max(1,n-20),n)]
    vol20 = statistics.pstdev(rs20)*math.sqrt(20)*100.0 if rs20 else 0.0
    return (mom(5), mom(20), mom(50), _trend_score(bars,20), flow5, flow20,
            _oi_change(bars,5), _oi_change(bars,20), _num(bars[-1].funding),
            _clamp(vol20,0.0,20.0), _volume_z(bars,20))


def _historical_feature_rows(bars, end):
    rows=[]
    for i in range(51, max(51,end)+1):
        rows.append((i,_feature_vector(bars[:i+1])))
    return rows


def _feature_scales(rows):
    if not rows:
        return (1.0,)*len(_FEATURE_NAMES)
    cols=list(zip(*(v for _,v in rows)))
    out=[]
    for col in cols:
        med=statistics.median(col)
        mad=statistics.median(abs(x-med) for x in col)
        out.append(max(1e-6,1.4826*mad,statistics.pstdev(col) or 0.0))
    return tuple(out)


def _distance(a,b,scales):
    return math.sqrt(sum(((x-y)/s)**2 for x,y,s in zip(a,b,scales))/len(a))


def _wilson_lower(p,n):
    if n <= 0:
        return 0.0
    z=_WILSON_Z
    denom=1.0+z*z/n
    centre=(p+z*z/(2*n))/denom
    half=z*math.sqrt(max(0.0,p*(1-p)/n+z*z/(4*n*n)))/denom
    return _clamp(centre-half,0.0,1.0)


def _analog_samples(bars,horizon,current,rows,scales):
    n=len(bars)
    end=n-horizon-1-(_EMBARGO_MULTIPLIER*horizon)
    if end < 51:
        return []
    ranked=[]
    for i,vec in rows:
        if i>end:
            break
        dist=_distance(current,vec,scales)
        ret=_ret(bars[i+horizon].price,bars[i].price)*100.0
        weight=1.0/(1.0+dist*dist)
        ranked.append((dist,ret,weight))
    ranked.sort(key=lambda x:x[0])
    chosen=ranked[:_MAX_ANALOGUES]
    if len(chosen)<_MIN_ANALOGUES:
        return []
    total=sum(x[2] for x in chosen)
    return [(ret,w/total) for _,ret,w in chosen]


def _weighted_mean(values,weights):
    total=sum(weights)
    return sum(v*w for v,w in zip(values,weights))/total if total else 0.0


def _forecast_one(bars,horizon,target_move_pct,current,rows,scales):
    rs=[_ret(bars[i].price,bars[i-1].price) for i in range(max(1,len(bars)-20),len(bars))]
    vol_pct=(statistics.pstdev(rs) or 1e-8)*math.sqrt(horizon)*100.0
    samples=_analog_samples(bars,horizon,current,rows,scales)
    if not samples:
        return HorizonForecast(horizon,"FLAT",0.0,0.0,-round(vol_pct,4),round(vol_pct,4),0.0,round(vol_pct,4),0.0)

    vals=[x for x,_ in samples]
    weights=[w for _,w in samples]
    p_up=sum(w for x,w in samples if x>0)
    p_down=sum(w for x,w in samples if x<0)
    effective_n=1.0/sum(w*w for w in weights)
    best_prob=max(p_up,p_down)
    edge=abs(p_up-p_down)
    lower_bound=_wilson_lower(best_prob,effective_n)

    if effective_n < _MIN_ANALOGUES or best_prob < 0.55 or lower_bound <= 0.50:
        direction="FLAT"
    else:
        direction="UP" if p_up>p_down else "DOWN"

    if direction=="FLAT":
        expected=0.0
        hit_prob=0.0
    else:
        mask=lambda x: x>0 if direction=="UP" else x<0
        favorable=[x for x in vals if mask(x)]
        fw=[w for x,w in samples if mask(x)]
        conditional=_weighted_mean(favorable,fw)
        shrink=_clamp((effective_n-20.0)/60.0,0.15,1.0)
        trend=_trend_score(bars,20)
        trend_component=(max(0.0,trend) if direction=="UP" else min(0.0,trend))*vol_pct*0.04
        expected=conditional*shrink+trend_component
        hit_prob=sum(w for x,w in samples if (x>=target_move_pct if direction=="UP" else x<=-target_move_pct))

    ladder = tuple(
        (float(t), round(sum(w for x,w in samples if (x >= t if direction == "UP" else x <= -t)), 4))
        for t in TARGET_LADDER_PCT
    ) if direction != "FLAT" else ()
    mean=_weighted_mean(vals,weights)
    variance=_weighted_mean([(x-mean)**2 for x in vals],weights)
    spread=math.sqrt(max(0.0,variance))
    lower=expected-spread
    upper=expected+spread
    adverse=max(0.0,-lower if direction=="UP" else upper if direction=="DOWN" else spread)
    confidence=_clamp(0.50+min(0.22,edge*0.80)+min(0.18,max(0.0,lower_bound-0.50)*2.0),0.34,0.90)
    if direction=="FLAT":
        confidence=0.0

    return HorizonForecast(
        horizon=horizon,
        direction=direction,
        confidence=round(confidence,4),
        expected_return_pct=round(_clamp(expected,-5.0,5.0),4),
        lower_return_pct=round(lower,4),
        upper_return_pct=round(upper,4),
        favorable_target_pct=round(abs(expected),4),
        adverse_move_pct=round(adverse,4),
        target_hit_probability=round(hit_prob,4),
        target_ladder_probability=ladder,
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
    current = _feature_vector(bars)
    rows = _historical_feature_rows(bars, len(bars) - 1)
    scales = _feature_scales(rows)
    forecasts = tuple(_forecast_one(bars, h, target_move_pct, current, rows, scales) for h in hs)
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
    round_trip_cost_pct: float = 0.35,
) -> dict:
    """Classify market opportunity independently of account capital.

    Capital and dollar-profit targets belong to position sizing/reporting, not
    to the market-edge gate. The only account-independent economic hurdle here
    is transaction cost.
    """
    cost_pct = max(0.0, float(round_trip_cost_pct))
    rows = []

    for f in path.horizons:
        expected_move = abs(f.expected_return_pct)
        expected_net_pct = expected_move - cost_pct
        ladder = dict(f.target_ladder_probability)

        # A target must clear round-trip cost to represent positive net payoff.
        eligible_targets = [
            (t, p) for t, p in f.target_ladder_probability
            if t > cost_pct
        ]
        selected_target, selected_prob = max(
            eligible_targets,
            key=lambda x: (x[1], x[0]),
            default=(0.0, 0.0),
        )
        target_net_pct = max(0.0, selected_target - cost_pct)
        break_even_target_probability = (
            cost_pct / selected_target if selected_target > 0.0 else 1.0
        )

        if f.direction == "FLAT":
            tier = "REJECT"
            reject_reason = "FLAT_FORECAST"
        elif f.confidence <= 0.0:
            tier = "REJECT"
            reject_reason = "ZERO_CONFIDENCE"
        elif selected_prob < 0.35:
            tier = "REJECT"
            reject_reason = "LOW_TARGET_HIT_PROBABILITY"
        elif expected_net_pct <= 0.0:
            tier = "REJECT"
            reject_reason = "INSUFFICIENT_NET_EXPECTED_MOVE"
        elif selected_prob >= 0.55:
            tier = "STRONG"
            reject_reason = ""
        elif selected_prob >= 0.45:
            tier = "VIABLE"
            reject_reason = ""
        else:
            tier = "WATCH"
            reject_reason = "WATCH_ONLY"

        rows.append({
            "horizon": f.horizon,
            "direction": f.direction,
            "confidence": f.confidence,
            "expected_return_pct": f.expected_return_pct,
            "expected_move_pct": expected_move,
            "expected_net_return_pct": round(expected_net_pct, 4),
            "target_hit_probability": f.target_hit_probability,
            "target_ladder_probability": {str(k): v for k, v in ladder.items()},
            "selected_target_pct": selected_target,
            "selected_target_hit_probability": selected_prob,
            "selected_target_net_pct_if_hit": round(target_net_pct, 4),
            "selected_target_break_even_probability": round(
                break_even_target_probability, 4
            ),
            "tier": tier,
            "reject_reason": reject_reason,
        })

    best = max(
        rows,
        key=lambda r: (
            r["expected_net_return_pct"],
            r["selected_target_hit_probability"],
        ),
        default=None,
    )
    return {
        "best": best,
        "horizons": rows,
        "minimum_required_net_move_pct": round(cost_pct, 4),
        "round_trip_cost_pct": round(cost_pct, 4),
        "economic_diagnostics_version": "target-net-payoff-v2-capital-independent",
        "economic_diagnostic_note": (
            "Opportunity classification is independent of account capital and "
            "dollar-profit targets. Dollar PnL belongs to position sizing/OOS "
            "reporting. selected_target_net_pct_if_hit is conditional on the "
            "target being reached and is not an expected profit."
        ),
        "research_only": True,
        "live_orders": False,
    }

