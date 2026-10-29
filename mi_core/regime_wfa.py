"""Research-only regime-filtered ATR/support-resistance walk-forward evaluation.

Signals are generated from the existing rolling OOS forecaster. Regime inputs
use only candles available at the signal close. Entry is the next candle open.
Dynamic exits are evaluated against OHLC; if both stop and target touch within
one candle, the stop is conservatively assumed first. Funding remains itemized
using the existing Hyperliquid event model, with candle-close oracle proxy and
explicit slippage assumptions. This module never places orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from .block_bootstrap import daily_block_bootstrap_mean_ci
from .hyperliquid_data import PerpCandle, FundingEvent, fetch_candles, fetch_funding_history, join_funding_feature
from .hyperliquid_wfa import trade_cost_components_pct, BASE_POLICY_COST_PCT, STRICT_POLICY_COST_PCT
from .models import MarketBar
from .validated_forecast import walk_forward_forecast


def _percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def calculate_regime(candles: list[PerpCandle], period: int = 14,
                     volatility_window: int = 100) -> list[dict[str, float | bool | None]]:
    """Causal ATR/ADX and ATR%-quantile regime; current bar is known at close."""
    if period < 2 or volatility_window < 30:
        raise ValueError("period must be >=2 and volatility_window >=30")
    n = len(candles)
    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i, c in enumerate(candles):
        prev_close = candles[i - 1].close if i else c.close
        tr[i] = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
        if i:
            up = c.high - candles[i - 1].high
            down = candles[i - 1].low - c.low
            plus_dm[i] = up if up > down and up > 0 else 0.0
            minus_dm[i] = down if down > up and down > 0 else 0.0

    out: list[dict[str, float | bool | None]] = []
    atr_pct_history: list[float] = []
    dx: list[float | None] = [None] * n
    atr_values: list[float | None] = [None] * n
    for i in range(n):
        if i + 1 >= period:
            atr = mean(tr[i - period + 1:i + 1])
            atr_values[i] = atr
            if i + 1 >= 2 * period - 1:
                sum_tr = sum(tr[i - period + 1:i + 1])
                pdi = 100.0 * sum(plus_dm[i - period + 1:i + 1]) / sum_tr if sum_tr else 0.0
                mdi = 100.0 * sum(minus_dm[i - period + 1:i + 1]) / sum_tr if sum_tr else 0.0
                den = pdi + mdi
                dx[i] = 100.0 * abs(pdi - mdi) / den if den else 0.0

    for i, c in enumerate(candles):
        atr = atr_values[i]
        atr_pct = 100.0 * atr / c.close if atr is not None and c.close > 0 else None
        adx = None
        if i >= 2 * period - 1:
            dx_window = [x for x in dx[i - period + 1:i + 1] if x is not None]
            if len(dx_window) == period:
                adx = mean(dx_window)
        history = atr_pct_history[-volatility_window:]
        enough = atr_pct is not None and len(history) >= 30 and adx is not None
        low_vol = _percentile(history, 0.10) if len(history) >= 30 else None
        high_vol = _percentile(history, 0.90) if len(history) >= 30 else None
        trend_ok = adx is not None and adx >= 22.0
        volatility_ok = bool(
            enough and low_vol is not None and high_vol is not None
            and low_vol <= atr_pct <= high_vol
        )
        out.append({
            "atr": atr, "atr_pct": atr_pct, "adx": adx,
            "atr_pct_p10_prior": low_vol, "atr_pct_p90_prior": high_vol,
            "trend_ok": trend_ok, "volatility_ok": volatility_ok,
            "regime_ok": bool(trend_ok and volatility_ok),
        })
        if atr_pct is not None:
            atr_pct_history.append(atr_pct)
    return out


def dynamic_levels(candles: list[PerpCandle], signal_index: int, entry_price: float,
                   side: int, atr: float, lookback: int = 20) -> dict[str, float]:
    """Set ATR risk distances and prior-window support/resistance; no future bars."""
    if side not in (-1, 1) or entry_price <= 0 or atr <= 0:
        raise ValueError("invalid side, entry price, or ATR")
    if signal_index < 0 or signal_index >= len(candles):
        raise ValueError("signal_index out of range")
    start = max(0, signal_index - lookback + 1)
    prior = candles[start:signal_index + 1]
    swing_low = min(c.low for c in prior)
    swing_high = max(c.high for c in prior)
    if side == 1:
        stop = min(entry_price - 1.5 * atr, swing_low - 0.1 * atr)
        target = max(entry_price + 2.0 * atr, swing_high + 0.25 * atr)
    else:
        stop = max(entry_price + 1.5 * atr, swing_high + 0.1 * atr)
        target = min(entry_price - 2.0 * atr, swing_low - 0.25 * atr)
    if stop <= 0 or (side == 1 and not stop < entry_price < target) or (side == -1 and not target < entry_price < stop):
        raise ValueError("dynamic levels are not ordered around entry")
    return {"stop": stop, "target": target, "atr": atr,
            "support": swing_low, "resistance": swing_high}


def _simulate_exit(candles: list[PerpCandle], entry_index: int, side: int,
                   stop: float, target: float, max_holding_bars: int) -> dict[str, Any]:
    """OHLC exit simulation; stop wins if stop and target touch in the same bar."""
    last_index = min(len(candles) - 1, entry_index + max_holding_bars - 1)
    for j in range(entry_index, last_index + 1):
        c = candles[j]
        if side == 1:
            stop_hit = c.low <= stop
            target_hit = c.high >= target
        else:
            stop_hit = c.high >= stop
            target_hit = c.low <= target
        if stop_hit:
            return {"exit_index": j, "exit_price": stop, "exit_reason": "STOP",
                    "same_bar_ambiguity": bool(target_hit)}
        if target_hit:
            return {"exit_index": j, "exit_price": target, "exit_reason": "TARGET",
                    "same_bar_ambiguity": False}
    c = candles[last_index]
    return {"exit_index": last_index, "exit_price": c.close, "exit_reason": "TIME",
            "same_bar_ambiguity": False}


def evaluate_regime_candles(
    coin: str, candles: list[PerpCandle], funding_events: list[FundingEvent], *,
    horizon: int = 24, train_window: int = 300, min_train: int = 60,
    fit_every: int = 10, atr_period: int = 14, adx_min: float = 22.0,
    volatility_window: int = 100, max_holding_bars: int = 24,
    maker_entry: bool = False, maker_exit: bool = False,
    maker_fee_rate: float = 0.00015, taker_fee_rate: float = 0.00045,
    slippage_bps_per_side: float = 2.0, bootstrap_resamples: int = 2000,
    seed: int = 20261029,
) -> dict[str, Any]:
    candles = sorted(candles, key=lambda c: c.timestamp_ms)
    if len(candles) < min_train + 25 + horizon + 2:
        return {"available": False, "status": "INSUFFICIENT_HISTORY",
                "bars": len(candles), "research_only": True, "live_orders": False}
    if len({c.timestamp_ms for c in candles}) != len(candles):
        raise ValueError("duplicate candle timestamps")
    if any(b.timestamp_ms <= a.timestamp_ms for a, b in zip(candles, candles[1:])):
        raise ValueError("candles must be strictly chronological")

    regimes = calculate_regime(candles, atr_period, volatility_window)
    funding_features = join_funding_feature(candles, funding_events)
    bars = [MarketBar(ts=c.close_time_ms, symbol=coin, price=c.close,
                      volume=c.volume, funding=funding_features[i],
                      open=c.open, high=c.high, low=c.low)
            for i, c in enumerate(candles)]
    forecast = walk_forward_forecast(bars, horizon=horizon,
                                    train_window=train_window,
                                    min_train=min_train, fit_every=fit_every)
    if not forecast.get("available"):
        return {**forecast, "status": "FORECAST_UNAVAILABLE",
                "research_only": True, "live_orders": False}

    by_close = {c.close_time_ms: i for i, c in enumerate(candles)}
    predictions = sorted(forecast.get("predictions", []), key=lambda r: r.get("ts", 0))
    # Sample forecast timestamps before applying regime/direction filters, so
    # filtered rows cannot make outcomes overlap.
    sampled_forecasts = predictions[::max(1, int(horizon))]
    trades: list[dict[str, Any]] = []
    rejected = {"flat_prediction": 0, "regime_filter": 0, "missing_next_bar": 0}
    for pred in sampled_forecasts:
        signal_i = by_close.get(int(pred.get("ts", -1)))
        if signal_i is None:
            continue
        side = int(pred.get("pred", 0))
        if side not in (-1, 1):
            rejected["flat_prediction"] += 1
            continue
        regime = regimes[signal_i]
        if not regime["trend_ok"] or not regime["volatility_ok"]:
            rejected["regime_filter"] += 1
            continue
        entry_i = signal_i + 1
        if entry_i >= len(candles) or entry_i + max_holding_bars > len(candles):
            rejected["missing_next_bar"] += 1
            continue
        entry = candles[entry_i].open
        atr = float(regime["atr"] or 0.0)
        levels = dynamic_levels(candles, signal_i, entry, side, atr)
        exit_info = _simulate_exit(candles, entry_i, side, levels["stop"],
                                   levels["target"], max_holding_bars)
        exit_i = int(exit_info["exit_index"])
        exit_price = float(exit_info["exit_price"])
        exit_candle = candles[exit_i]
        entry_candle = candles[entry_i]
        gross_pct = side * (exit_price / entry - 1.0) * 100.0
        costs = trade_cost_components_pct(
            entry_price=entry, exit_price=exit_price, side=side,
            funding_events=funding_events, candles=candles,
            maker_entry=maker_entry, maker_exit=maker_exit,
            maker_fee_rate=maker_fee_rate, taker_fee_rate=taker_fee_rate,
            slippage_bps_per_side=slippage_bps_per_side,
            entry_ts=entry_candle.timestamp_ms,
            # Conservative boundary: include events through exit-candle close,
            # since OHLC cannot identify the exact intrabar exit timestamp.
            exit_ts=exit_candle.close_time_ms,
        )
        net_pct = gross_pct - costs["total_itemized_cost_pct"]
        trades.append({
            "ts": entry_candle.timestamp_ms, "signal_ts": int(pred["ts"]),
            "exit_ts": exit_candle.close_time_ms, "side": side,
            "entry_price": entry, "exit_price": exit_price,
            "gross_return_pct": gross_pct, "net_return_pct": net_pct,
            "policy_base_015_net_pct": gross_pct - BASE_POLICY_COST_PCT,
            "policy_stress_045_net_pct": gross_pct - STRICT_POLICY_COST_PCT,
            "exit_reason": exit_info["exit_reason"],
            "same_bar_ambiguity": exit_info["same_bar_ambiguity"],
            "stop": levels["stop"], "target": levels["target"],
            "atr_at_signal": atr, "adx_at_signal": regime["adx"],
            "atr_pct_at_signal": regime["atr_pct"],
            "support_at_signal": levels["support"],
            "resistance_at_signal": levels["resistance"],
            **costs,
        })

    net = [t["net_return_pct"] for t in trades]
    gross = [t["gross_return_pct"] for t in trades]
    losses = abs(sum(v for v in net if v < 0))
    bootstrap = daily_block_bootstrap_mean_ci(
        [(int(t["ts"]), float(t["net_return_pct"])) for t in trades],
        n_resamples=bootstrap_resamples, block_days=1, seed=seed,
    ) if trades else {"status": "NO_TRADES", "mean_pct": None,
                      "ci_low_pct": None, "ci_high_pct": None,
                      "n_trades": 0, "n_days": 0}
    sensitivity = {
        str(days): daily_block_bootstrap_mean_ci(
            [(int(t["ts"]), float(t["net_return_pct"])) for t in trades],
            n_resamples=bootstrap_resamples, block_days=days, seed=seed,
        ) if trades else {"status": "NO_TRADES", "mean_pct": None,
                          "ci_low_pct": None, "ci_high_pct": None,
                          "n_trades": 0, "n_days": 0, "block_days": days}
        for days in (1, 3, 7)
    }
    return {
        "available": True, "status": "OK" if trades else "NO_TRADES",
        "mode": "regime_atr_support_resistance_wfa_research_only",
        "coin": coin, "bars": len(candles), "forecast_count": len(predictions),
        "sampled_forecast_count": len(sampled_forecasts),
        "trade_count": len(trades), "rejected_counts": rejected,
        "gross_mean_pct": mean(gross) if gross else None,
        "net_itemized_mean_pct": mean(net) if net else None,
        "net_itemized_sum_pct": sum(net),
        "positive_net_rate": sum(v > 0 for v in net) / len(net) if net else None,
        "profit_factor": sum(v for v in net if v > 0) / losses if losses else None,
        "exit_reason_counts": {reason: sum(t["exit_reason"] == reason for t in trades)
                               for reason in ("STOP", "TARGET", "TIME")},
        "same_bar_ambiguity_count": sum(bool(t["same_bar_ambiguity"]) for t in trades),
        "block_bootstrap_mean_ci": bootstrap,
        "block_bootstrap_sensitivity": sensitivity,
        "policy_sensitivity": {
            "fixed_cost_base_015_mean_net_pct": mean([t["policy_base_015_net_pct"] for t in trades]) if trades else None,
            "fixed_cost_stress_045_mean_net_pct": mean([t["policy_stress_045_net_pct"] for t in trades]) if trades else None,
            "warning": "fixed cost sensitivities are separate from itemized costs; do not add them together",
        },
        "indicator_policy": {
            "atr_period": atr_period, "adx_min": adx_min,
            "volatility_window": volatility_window,
            "volatility_filter": "ATR percent must be within prior rolling p10-p90",
            "stop": "more conservative of 1.5 ATR and prior 20-bar swing with 0.1 ATR buffer",
            "target": "farther of 2 ATR and prior 20-bar swing with 0.25 ATR buffer",
            "entry": "next candle open after forecast candle close",
            "same_candle_stop_target": "stop assumed first",
        },
        "cost_model": {
            "maker_entry": maker_entry, "maker_exit": maker_exit,
            "maker_fee_rate_per_side": maker_fee_rate,
            "taker_fee_rate_per_side": taker_fee_rate,
            "slippage_bps_per_side": slippage_bps_per_side,
            "slippage_source": "assumption, not observed fills",
            "funding_source": "discrete historical Hyperliquid funding events",
            "funding_price_source": "nearest prior candle close proxy, not oracle-exact",
            "funding_exit_boundary": "events through exit candle close included conservatively",
        },
        "data_source": {"venue": "Hyperliquid", "instrument": "perpetual",
                        "first_candle_ms": candles[0].timestamp_ms,
                        "last_candle_ms": candles[-1].close_time_ms,
                        "funding_events": len(funding_events)},
        "trade_sample": trades[:10],
        "research_only": True, "live_orders": False,
    }


def run_regime_wfa(coin: str, interval: str, start_ms: int, end_ms: int,
                   **kwargs: Any) -> dict[str, Any]:
    candles = fetch_candles(coin, interval, start_ms, end_ms)
    funding = fetch_funding_history(coin, start_ms, end_ms)
    result = evaluate_regime_candles(coin, candles, funding, **kwargs)
    result.setdefault("data_source", {})
    result["data_source"].update({"requested_start_ms": int(start_ms),
                                  "requested_end_ms": int(end_ms)})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research-only regime/ATR Hyperliquid WFA")
    parser.add_argument("--coin", default="BTC")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--start-ms", type=int, required=True)
    parser.add_argument("--end-ms", type=int, required=True)
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--train-window", type=int, default=300)
    parser.add_argument("--min-train", type=int, default=60)
    parser.add_argument("--max-holding-bars", type=int, default=24)
    parser.add_argument("--slippage-bps-per-side", type=float, default=2.0)
    parser.add_argument("--bootstrap-resamples", type=int, default=2000)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    result = run_regime_wfa(
        args.coin, args.interval, args.start_ms, args.end_ms,
        horizon=args.horizon, train_window=args.train_window,
        min_train=args.min_train, max_holding_bars=args.max_holding_bars,
        slippage_bps_per_side=args.slippage_bps_per_side,
        bootstrap_resamples=args.bootstrap_resamples,
    )
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")
        print(target)
        print(json.dumps({k: result.get(k) for k in (
            "available", "status", "bars", "trade_count", "gross_mean_pct",
            "net_itemized_mean_pct", "net_itemized_sum_pct", "positive_net_rate",
            "profit_factor", "rejected_counts", "exit_reason_counts",
            "block_bootstrap_mean_ci", "block_bootstrap_sensitivity",
            "policy_sensitivity", "data_source", "research_only", "live_orders")}, indent=2))
    else:
        print(payload)
    return 0 if result.get("available") else 2


if __name__ == "__main__":
    raise SystemExit(main())
