"""Research-only walk-forward evaluation on Hyperliquid perpetual candles.

Primary net returns use configurable per-side maker/taker fees, an explicit
slippage assumption, and historical discrete funding events. Candle close is
only a proxy for the historical oracle price at funding time; candle data does
not reveal historical executable fills or observed slippage. Fixed 0.15% and
0.45% cost cases are reported separately as policy sensitivities, never added
to the itemized cost model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from .block_bootstrap import daily_block_bootstrap_mean_ci
from .hyperliquid_data import FundingEvent, PerpCandle, _post_info, fetch_candles, fetch_funding_history, join_funding_feature
from .models import MarketBar
from .validated_forecast import walk_forward_forecast

BASE_POLICY_COST_PCT = 0.15
STRICT_POLICY_COST_PCT = 0.45


def trade_cost_components_pct(
    *,
    entry_price: float,
    exit_price: float,
    side: int,
    funding_events: list[FundingEvent],
    candles: list[PerpCandle],
    maker_entry: bool = False,
    maker_exit: bool = False,
    maker_fee_rate: float = 0.00015,
    taker_fee_rate: float = 0.00045,
    slippage_bps_per_side: float = 2.0,
    entry_ts: int,
    exit_ts: int,
) -> dict[str, float]:
    """Return costs as percentage of entry notional for a unit-size position."""
    if side not in (-1, 1):
        raise ValueError("side must be +1 or -1")
    if entry_price <= 0 or exit_price <= 0:
        raise ValueError("entry and exit prices must be positive")
    if maker_fee_rate < 0 or taker_fee_rate < 0 or slippage_bps_per_side < 0:
        raise ValueError("fee and slippage assumptions must be non-negative")
    if exit_ts <= entry_ts:
        raise ValueError("exit_ts must be later than entry_ts")

    entry_rate = maker_fee_rate if maker_entry else taker_fee_rate
    exit_rate = maker_fee_rate if maker_exit else taker_fee_rate
    exit_notional_ratio = exit_price / entry_price
    fee_pct = 100.0 * (entry_rate + exit_rate * exit_notional_ratio)
    slippage_pct = (slippage_bps_per_side / 100.0) * (1.0 + exit_notional_ratio)

    ordered_candles = sorted(candles, key=lambda candle: candle.timestamp_ms)
    eligible_events = [
        event for event in funding_events
        if entry_ts < event.timestamp_ms <= exit_ts
    ]
    funding_cost_pct = 0.0
    for event in eligible_events:
        proxy = None
        for candle in ordered_candles:
            if candle.close_time_ms > event.timestamp_ms:
                break
            proxy = candle.close
        if proxy is None:
            raise ValueError("no candle available to proxy oracle price at funding event")
        # Hyperliquid funding is paid hourly using oracle-price notional. Candle
        # close is explicitly a proxy here, not a claimed historical oracle.
        funding_cost_pct += side * event.rate * proxy / entry_price * 100.0

    return {
        "fee_pct": fee_pct,
        "slippage_pct": slippage_pct,
        "funding_cost_pct": funding_cost_pct,
        "total_itemized_cost_pct": fee_pct + slippage_pct + funding_cost_pct,
        "funding_events_count": float(len(eligible_events)),
        "slippage_is_assumption": 1.0,
        "funding_price_is_candle_proxy": 1.0 if eligible_events else 0.0,
    }


def _trade_net_row(
    prediction: dict[str, Any],
    candles: list[PerpCandle],
    funding_events: list[FundingEvent],
    horizon: int,
    *,
    maker_entry: bool,
    maker_exit: bool,
    maker_fee_rate: float,
    taker_fee_rate: float,
    slippage_bps_per_side: float,
) -> dict[str, Any] | None:
    by_ts = {candle.close_time_ms: i for i, candle in enumerate(candles)}
    entry_ts = int(prediction.get("ts", -1))
    if entry_ts not in by_ts:
        return None
    entry_idx = by_ts[entry_ts]
    exit_idx = entry_idx + int(horizon)
    if exit_idx >= len(candles):
        return None
    entry = candles[entry_idx]
    exit_ = candles[exit_idx]
    side = int(prediction.get("pred", 0))
    if side not in (-1, 1):
        return None
    gross_pct = side * (exit_.close / entry.close - 1.0) * 100.0
    costs = trade_cost_components_pct(
        entry_price=entry.close, exit_price=exit_.close, side=side,
        funding_events=funding_events, candles=candles,
        maker_entry=maker_entry, maker_exit=maker_exit,
        maker_fee_rate=maker_fee_rate, taker_fee_rate=taker_fee_rate,
        slippage_bps_per_side=slippage_bps_per_side,
        entry_ts=entry.close_time_ms, exit_ts=exit_.close_time_ms,
    )
    return {
        "ts": entry.close_time_ms,
        "exit_ts": exit_.close_time_ms,
        "side": side,
        "entry_price": entry.close,
        "exit_price": exit_.close,
        "gross_return_pct": gross_pct,
        "actual_return_pct": gross_pct,
        **costs,
        "net_return_pct": gross_pct - costs["total_itemized_cost_pct"],
        "policy_base_015_net_pct": gross_pct - BASE_POLICY_COST_PCT,
        "policy_stress_045_net_pct": gross_pct - STRICT_POLICY_COST_PCT,
    }


def evaluate_candles(
    coin: str,
    candles: list[PerpCandle],
    funding_events: list[FundingEvent],
    *,
    horizon: int = 60,
    train_window: int = 300,
    min_train: int = 60,
    fit_every: int = 10,
    maker_entry: bool = False,
    maker_exit: bool = False,
    maker_fee_rate: float = 0.00015,
    taker_fee_rate: float = 0.00045,
    slippage_bps_per_side: float = 2.0,
    bootstrap_resamples: int = 10_000,
    block_days: int = 1,
    seed: int = 20261029,
) -> dict[str, Any]:
    """Run existing rolling WFA model on supplied Hyperliquid perpetual candles."""
    candles = sorted(candles, key=lambda candle: candle.timestamp_ms)
    if len(candles) < min_train + 25 + horizon:
        return {
            "available": False, "reason": "insufficient_hyperliquid_history",
            "bars": len(candles), "required_minimum": min_train + 25 + horizon,
            "research_only": True, "live_orders": False,
        }
    if len({c.timestamp_ms for c in candles}) != len(candles):
        raise ValueError("duplicate candle timestamps must be resolved before WFA")
    if any(b.timestamp_ms <= a.timestamp_ms for a, b in zip(candles, candles[1:])):
        raise ValueError("candles must be strictly chronological")

    features = join_funding_feature(candles, funding_events)
    bars = [
        MarketBar(
            ts=c.close_time_ms, symbol=coin, price=c.close, volume=c.volume,
            funding=features[i], open=c.open, high=c.high, low=c.low,
        )
        for i, c in enumerate(candles)
    ]
    raw = walk_forward_forecast(
        bars, horizon=horizon, train_window=train_window,
        min_train=min_train, fit_every=fit_every,
    )
    if not raw.get("available"):
        return {**raw, "mode": "hyperliquid_perpetual_wfa", "research_only": True, "live_orders": False}

    raw_predictions = sorted(raw.get("predictions", []), key=lambda row: row.get("ts", 0))
    # Sample the full forecast timeline first, before dropping FLAT predictions.
    # Otherwise filtering FLAT rows first could accidentally reintroduce overlap.
    selected_ts = {
        int(row["ts"]) for row in raw_predictions[::max(1, int(horizon))]
        if row.get("pred") in (-1, 1) and row.get("actual_return_pct") is not None
    }
    sampled = []
    for prediction in raw_predictions:
        if int(prediction.get("ts", -1)) not in selected_ts:
            continue
        row = _trade_net_row(
            prediction, candles, funding_events, horizon,
            maker_entry=maker_entry, maker_exit=maker_exit,
            maker_fee_rate=maker_fee_rate, taker_fee_rate=taker_fee_rate,
            slippage_bps_per_side=slippage_bps_per_side,
        )
        if row is not None:
            sampled.append(row)
    net = [float(row["net_return_pct"]) for row in sampled]
    gross = [float(row["gross_return_pct"]) for row in sampled]
    base = [float(row["policy_base_015_net_pct"]) for row in sampled]
    stress = [float(row["policy_stress_045_net_pct"]) for row in sampled]
    block_ci = daily_block_bootstrap_mean_ci(
        [(int(row["ts"]), float(row["net_return_pct"])) for row in sampled],
        n_resamples=bootstrap_resamples, block_days=block_days, seed=seed,
    ) if sampled else {
        "status": "NO_TRADES", "mean_pct": None, "ci_low_pct": None, "ci_high_pct": None,
        "n_trades": 0, "n_days": 0,
    }
    wins = sum(value > 0 for value in net)
    losses = abs(sum(value for value in net if value < 0))
    equity = peak = 1.0
    max_dd_pct = 0.0
    for value in net:
        equity *= 1.0 + value / 100.0
        peak = max(peak, equity)
        if peak > 0:
            max_dd_pct = max(max_dd_pct, (peak - equity) / peak * 100.0)
    return {
        "available": bool(sampled),
        "mode": "hyperliquid_perpetual_walk_forward_oos",
        "coin": coin, "bars": len(candles), "horizon_bars": horizon,
        "model_version": raw.get("model_version"),
        "predictions_generated": len(raw.get("predictions", [])),
        "directional_nonoverlap_trades": len(sampled),
        "gross_mean_pct": sum(gross) / len(gross) if gross else None,
        "net_itemized_mean_pct": sum(net) / len(net) if net else None,
        "net_itemized_sum_pct": sum(net),
        "positive_net_rate": wins / len(net) if net else None,
        "profit_factor": sum(v for v in net if v > 0) / losses if losses else None,
        "compounded_trade_sequence_drawdown_pct": max_dd_pct,
        "policy_sensitivity": {
            "fixed_cost_base_015_mean_net_pct": sum(base) / len(base) if base else None,
            "fixed_cost_stress_045_mean_net_pct": sum(stress) / len(stress) if stress else None,
            "warning": "policy sensitivity is separate from itemized fees/slippage/funding; do not add the two models together",
        },
        "block_bootstrap_mean_ci": block_ci,
        "cost_model": {
            "maker_entry": maker_entry, "maker_exit": maker_exit,
            "maker_fee_rate_per_side": maker_fee_rate,
            "taker_fee_rate_per_side": taker_fee_rate,
            "slippage_bps_per_side": slippage_bps_per_side,
            "slippage_source": "explicit_model_assumption_not_observed_historical_fills",
            "funding_source": "Hyperliquid historical fundingHistory endpoint",
            "funding_price_source": "nearest prior candle close proxy; true historical oracle price not supplied by candle endpoint",
            "funding_payment_frequency": "discrete historical events; no forward carry or look-ahead",
        },
        "data_source": {
            "venue": "Hyperliquid", "instrument": "perpetual",
            "candles": "public candleSnapshot API", "funding": "public fundingHistory API",
            "first_candle_ms": candles[0].close_time_ms,
            "last_candle_ms": candles[-1].close_time_ms,
            "funding_events": len(funding_events),
        },
        "trade_sample": sampled[:5],
        "research_only": True, "live_orders": False,
    }


def run_hyperliquid_wfa(
    coin: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    **kwargs: Any,
) -> dict[str, Any]:
    """Fetch public Hyperliquid candles/funding then evaluate the rolling WFA."""
    candles = fetch_candles(coin, interval, start_ms, end_ms)
    funding = fetch_funding_history(coin, start_ms, end_ms)
    result = evaluate_candles(coin, candles, funding, **kwargs)
    result.setdefault("data_source", {})
    result["data_source"]["requested_start_ms"] = int(start_ms)
    result["data_source"]["requested_end_ms"] = int(end_ms)
    expected_funding_hours = max(0, (int(end_ms) - int(start_ms)) // 3_600_000)
    if funding:
        first_funding_ms = funding[0].timestamp_ms
        last_funding_ms = funding[-1].timestamp_ms
        funding_spans_range = (
            first_funding_ms <= int(start_ms) + 2 * 3_600_000
            and last_funding_ms >= int(end_ms) - 2 * 3_600_000
        )
        funding_count_ok = expected_funding_hours == 0 or len(funding) >= 0.95 * expected_funding_hours
        funding_status = "WITHIN_TWO_HOURS_AND_95_PERCENT" if funding_spans_range and funding_count_ok else "PARTIAL_OR_UNVERIFIED"
    else:
        first_funding_ms = last_funding_ms = None
        funding_status = "NO_FUNDING_EVENTS"
    result["data_source"]["funding_coverage_check"] = {
        "status": funding_status,
        "expected_approx_hourly_events": expected_funding_hours,
        "observed_events": len(funding),
        "first_event_ms": first_funding_ms,
        "last_event_ms": last_funding_ms,
        "warning": "Funding event coverage is checked heuristically; this is not proof that no event is missing.",
    }
    interval_ms = {
        "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
        "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
        "4h": 14_400_000, "8h": 28_800_000, "12h": 43_200_000,
        "1d": 86_400_000, "3d": 259_200_000, "1w": 604_800_000,
    }.get(interval)
    if candles and interval_ms:
        start_observed = candles[0].timestamp_ms
        end_observed = candles[-1].close_time_ms
        complete = (
            start_observed <= int(start_ms) + interval_ms
            and end_observed >= int(end_ms) - interval_ms
        )
        result["data_source"]["coverage_check"] = {
            "status": "WITHIN_ONE_BAR_TOLERANCE" if complete else "PARTIAL_OR_UNVERIFIED",
            "first_candle_start_ms": start_observed,
            "last_candle_close_ms": end_observed,
            "tolerance_ms": interval_ms,
            "warning": "This is a boundary check, not proof that every candle or funding event is present.",
        }
    else:
        result["data_source"]["coverage_check"] = {
            "status": "UNVERIFIED",
            "warning": "No candles returned or interval coverage tolerance unavailable.",
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research-only Hyperliquid perpetual WFA")
    parser.add_argument("--coin", required=True, help="Hyperliquid coin symbol, e.g. BTC")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--start-ms", type=int, required=True, help="UTC epoch milliseconds")
    parser.add_argument("--end-ms", type=int, required=True, help="UTC epoch milliseconds")
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--train-window", type=int, default=300)
    parser.add_argument("--min-train", type=int, default=60)
    parser.add_argument("--maker-entry", action="store_true", help="model entry as maker; default is taker")
    parser.add_argument("--maker-exit", action="store_true", help="model exit as maker; default is taker")
    parser.add_argument("--maker-fee-rate", type=float, default=0.00015, help="decimal fee rate per maker side")
    parser.add_argument("--taker-fee-rate", type=float, default=0.00045, help="decimal fee rate per taker side")
    parser.add_argument("--slippage-bps-per-side", type=float, default=2.0, help="explicit assumption, not measured historical slippage")
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    parser.add_argument("--block-days", type=int, default=1)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    result = run_hyperliquid_wfa(
        args.coin, args.interval, args.start_ms, args.end_ms,
        horizon=args.horizon, train_window=args.train_window,
        min_train=args.min_train, maker_entry=args.maker_entry, maker_exit=args.maker_exit,
        maker_fee_rate=args.maker_fee_rate, taker_fee_rate=args.taker_fee_rate,
        slippage_bps_per_side=args.slippage_bps_per_side,
        bootstrap_resamples=args.bootstrap_resamples, block_days=args.block_days,
    )
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")
        print(target)
    else:
        print(payload)
    return 0 if result.get("available") else 2


if __name__ == "__main__":
    raise SystemExit(main())
