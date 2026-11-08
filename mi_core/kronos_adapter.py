"""Optional Kronos foundation-model adapter for Project60.

The upstream Kronos repository is loaded lazily from a separate checkout.
This module has no mandatory third-party imports and never places orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import importlib
import math
import os
from pathlib import Path
import sys
import statistics
from typing import Iterable, Sequence

from .models import MarketBar


@dataclass(frozen=True)
class KronosConfig:
    repo_path: str
    model_name: str = "NeoQuasar/Kronos-mini"
    tokenizer_name: str = "NeoQuasar/Kronos-Tokenizer-2k"
    max_context: int = 2048
    pred_len: int = 24
    interval_minutes: int = 60
    scenario_count: int = 20
    batch_size: int = 4
    device: str = "cpu"
    temperature: float = 1.0
    top_p: float = 0.9

    def __post_init__(self) -> None:
        if not str(self.repo_path).strip():
            raise ValueError("repo_path is required; clone the official Kronos repository separately")
        if self.max_context < 32 or self.max_context > 2048:
            raise ValueError("max_context must be between 32 and 2048")
        if not 1 <= self.pred_len <= 256:
            raise ValueError("pred_len must be between 1 and 256")
        if self.interval_minutes <= 0:
            raise ValueError("interval_minutes must be positive")
        if not 1 <= self.scenario_count <= 100:
            raise ValueError("scenario_count must be between 1 and 100")
        if not 1 <= self.batch_size <= 16:
            raise ValueError("batch_size must be between 1 and 16")
        if not math.isfinite(float(self.temperature)) or self.temperature <= 0:
            raise ValueError("temperature must be finite and positive")
        if not 0 < float(self.top_p) <= 1:
            raise ValueError("top_p must be in (0, 1]")


def validate_ohlcv_bars(bars: Sequence[MarketBar], min_bars: int = 32) -> list[MarketBar]:
    """Fail closed: never synthesize OHLC from close-only Project60 snapshots."""
    rows = list(bars)
    if len(rows) < min_bars:
        raise ValueError(f"insufficient_history:{len(rows)}<{min_bars}")
    previous_ts = None
    for index, bar in enumerate(rows):
        values = (bar.open, bar.high, bar.low, bar.price)
        if any(value is None for value in values):
            raise ValueError(f"missing_ohlc:{index}")
        o, h, low, close = (float(value) for value in values)
        if any(not math.isfinite(value) or value <= 0 for value in (o, h, low, close)):
            raise ValueError(f"invalid_ohlc:{index}")
        if low > min(o, close) or h < max(o, close) or low > h:
            raise ValueError(f"inconsistent_ohlc:{index}")
        volume = float(bar.volume or 0.0)
        if not math.isfinite(volume) or volume < 0:
            raise ValueError(f"invalid_volume:{index}")
        ts = int(bar.ts)
        if previous_ts is not None and ts <= previous_ts:
            raise ValueError(f"timestamps_not_strictly_increasing:{index}")
        previous_ts = ts
    return rows


def validate_bar_interval(bars: Sequence[MarketBar], interval_minutes: int) -> None:
    """Reject missing/irregular candles instead of silently forecasting across gaps."""
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive")
    if len(bars) < 2:
        raise ValueError("insufficient_history_for_interval_check")
    unit = 1000 if abs(int(bars[-1].ts)) >= 100_000_000_000 else 1
    expected = int(interval_minutes) * 60 * unit
    for index in range(1, len(bars)):
        if int(bars[index].ts) - int(bars[index - 1].ts) != expected:
            raise ValueError(f"irregular_bar_interval:{index}")


def summarize_scenarios(paths: Sequence[Sequence[dict]]) -> dict:
    """Summarize independent paths without treating scenario frequency as calibrated probability."""
    if not paths:
        raise ValueError("no_scenarios")
    horizon_len = len(paths[0])
    if horizon_len == 0 or any(len(path) != horizon_len for path in paths):
        raise ValueError("scenario_horizon_mismatch")
    summary = []
    for step in range(horizon_len):
        closes = [float(path[step]["close"]) for path in paths]
        if any(not math.isfinite(value) or value <= 0 for value in closes):
            raise ValueError(f"invalid_scenario_close:{step}")
        ordered = sorted(closes)

        def quantile(q: float) -> float:
            position = (len(ordered) - 1) * q
            lower = int(math.floor(position))
            upper = int(math.ceil(position))
            if lower == upper:
                return ordered[lower]
            return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

        summary.append({
            "step": step + 1,
            "close_median": quantile(0.50),
            "close_p10": quantile(0.10),
            "close_p90": quantile(0.90),
            "up_path_fraction": sum(value > paths[0][0].get("reference_close", value) for value in closes) / len(closes),
        })
    return {"scenario_count": len(paths), "horizon_bars": horizon_len, "summary": summary}


def load_project60_ohlc(path: str, asset: str = "BTC", max_rows: int = 800) -> list[MarketBar]:
    """Load explicit OHLCV fields from Project60 JSONL; close-only snapshots are rejected."""
    import json

    if max_rows < 32:
        raise ValueError("max_rows must be at least 32")
    rows: list[MarketBar] = []
    source = Path(path)
    for line in source.read_text(encoding="utf-8").splitlines()[-max_rows:]:
        try:
            record = json.loads(line)
            coins = record.get("coins", {})
            if isinstance(coins, list):
                coins = {str(item.get("coin")): item for item in coins if isinstance(item, dict)}
            item = coins.get(asset) or coins.get(asset.upper())
            if not isinstance(item, dict):
                continue
            candle = item.get("ohlcv") or item.get("ohlc") or item.get("candle") or item
            if not isinstance(candle, dict):
                continue
            close = candle.get("close")
            if close is None:
                close = item.get("close")
            if close is None and item.get("price") is not None:
                # A spot snapshot price is not a candle close unless OHLC is explicit.
                if all(candle.get(key) is not None for key in ("open", "high", "low")):
                    close = item.get("price")
            if any(candle.get(key) is None for key in ("open", "high", "low")) or close is None:
                continue
            timestamp = record.get("timestamp", item.get("timestamp", item.get("ts")))
            if timestamp is None:
                continue
            trades = item.get("trades") or {}
            volume = candle.get("volume", item.get("volume", trades.get("volume", 0.0)))
            rows.append(MarketBar(
                ts=int(float(timestamp)),
                symbol=asset.upper(),
                price=float(close),
                volume=float(volume or 0.0),
                open=float(candle["open"]),
                high=float(candle["high"]),
                low=float(candle["low"]),
            ))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return validate_ohlcv_bars(rows)


def _load_upstream(config: KronosConfig):
    root = Path(config.repo_path).expanduser().resolve()
    if not (root / "model" / "kronos.py").is_file() or not (root / "model" / "module.py").is_file():
        raise FileNotFoundError("invalid_kronos_repo_path: expected model/kronos.py and model/module.py")
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    module = importlib.import_module("model.kronos")
    tokenizer_class = getattr(module, "KronosTokenizer")
    model_class = getattr(module, "Kronos")
    predictor_class = getattr(module, "KronosPredictor")
    tokenizer = tokenizer_class.from_pretrained(config.tokenizer_name)
    model = model_class.from_pretrained(config.model_name)
    model.eval()
    tokenizer.eval()
    return predictor_class(model, tokenizer, device=config.device, max_context=config.max_context)


def forecast_kronos(
    bars: Sequence[MarketBar],
    config: KronosConfig,
    predictor=None,
) -> dict:
    """Generate independent OHLCV paths in bounded batches using upstream predict_batch."""
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Kronos optional dependencies missing; install the kronos extra and upstream requirements") from exc

    rows = validate_ohlcv_bars(bars)
    context = rows[-config.max_context:]
    validate_bar_interval(context, config.interval_minutes)
    last_ts = int(context[-1].ts)
    timestamp_unit = "ms" if abs(last_ts) >= 100_000_000_000 else "s"
    x_timestamps = pd.to_datetime([bar.ts for bar in context], unit=timestamp_unit, utc=True)
    step = timedelta(minutes=config.interval_minutes)
    last_dt = x_timestamps[-1].to_pydatetime()
    y_timestamps = pd.date_range(
        start=last_dt + step, periods=config.pred_len,
        freq=pd.Timedelta(minutes=config.interval_minutes), tz="UTC"
    )
    frame = pd.DataFrame({
        "open": [float(bar.open) for bar in context],
        "high": [float(bar.high) for bar in context],
        "low": [float(bar.low) for bar in context],
        "close": [float(bar.price) for bar in context],
        "volume": [float(bar.volume or 0.0) for bar in context],
    })
    if predictor is None:
        predictor = _load_upstream(config)

    paths: list[list[dict]] = []
    for offset in range(0, config.scenario_count, config.batch_size):
        count = min(config.batch_size, config.scenario_count - offset)
        frames = [frame.copy() for _ in range(count)]
        x_series = [pd.Series(x_timestamps) for _ in range(count)]
        y_series = [pd.Series(y_timestamps) for _ in range(count)]
        predictions = predictor.predict_batch(
            df_list=frames,
            x_timestamp_list=x_series,
            y_timestamp_list=y_series,
            pred_len=config.pred_len,
            T=config.temperature,
            top_p=config.top_p,
            sample_count=1,
            verbose=False,
        )
        for predicted in predictions:
            path = []
            for timestamp, row in predicted.iterrows():
                values = {key: float(row[key]) for key in ("open", "high", "low", "close", "volume")}
                if any(not math.isfinite(value) for value in values.values()):
                    raise ValueError("non_finite_model_output")
                if values["low"] > min(values["open"], values["close"]) or values["high"] < max(values["open"], values["close"]) or values["low"] > values["high"]:
                    raise ValueError("inconsistent_predicted_ohlc")
                path.append({"timestamp": timestamp.isoformat(), **values})
            if len(path) != config.pred_len:
                raise ValueError("unexpected_prediction_length")
            path[0]["reference_close"] = float(context[-1].price)
            paths.append(path)

    summary = summarize_scenarios(paths)
    final_closes = [path[-1]["close"] for path in paths]
    reference = float(context[-1].price)
    returns = [(value / reference - 1.0) * 100.0 for value in final_closes]
    up_fraction = sum(value > 0 for value in returns) / len(returns)
    return {
        "available": True,
        "model": "Kronos",
        "model_name": config.model_name,
        "tokenizer_name": config.tokenizer_name,
        "asset": context[-1].symbol,
        "as_of_ts": context[-1].ts,
        "reference_close": reference,
        "pred_len": config.pred_len,
        "scenario_count": len(paths),
        "scenario_up_fraction": round(up_fraction, 4),
        "scenario_return_p10_pct": round(sorted(returns)[max(0, math.floor((len(returns)-1)*0.10))], 4),
        "scenario_return_median_pct": round(statistics.median(returns), 4),
        "scenario_return_p90_pct": round(sorted(returns)[min(len(returns)-1, math.ceil((len(returns)-1)*0.90))], 4),
        "paths": paths,
        "summary": summary["summary"],
        "interpretation": "sample-path frequency is descriptive, not a calibrated probability",
        "data_quality": "explicit_ohlcv_only",
        "research_only": True,
        "live_orders": False,
    }
