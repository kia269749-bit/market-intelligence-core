"""Append-only shadow journal and lightweight outcome resolution."""
from __future__ import annotations
import json
import time
from bisect import bisect_right
from pathlib import Path

def append_signal(path: str, signal: dict) -> bool:
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    signal_id=signal.get("signal_id")
    if signal_id and p.exists():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    row=json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("signal_id")==signal_id:
                    return False
        except OSError:
            return False
    record={"ts":int(time.time()),"status":"OPEN",**signal}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False)+"\n")
    return True

def resolve_signal(entry_price: float, current_price: float, direction: str,
                   stop: float, target: float) -> str:
    d=str(direction).upper()
    if d=="BULLISH":
        if current_price <= stop: return "STOP"
        if current_price >= target: return "TARGET"
    elif d=="BEARISH":
        if current_price >= stop: return "STOP"
        if current_price <= target: return "TARGET"
    return "OPEN"

def _project60_sample_timestamps(path: str | None) -> dict[str, list[int]]:
    """Load valid timestamps for each asset from Project60 JSONL history."""
    result: dict[str, list[int]] = {}
    if not path:
        return result
    try:
        with Path(path).open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                    ts = int(record["timestamp"])
                    coins = record.get("coins", {})
                    if isinstance(coins, list):
                        coins = {
                            str(item.get("coin", "")).upper(): item
                            for item in coins if isinstance(item, dict)
                        }
                    if not isinstance(coins, dict):
                        continue
                    for asset, item in coins.items():
                        if not isinstance(item, dict):
                            continue
                        price = float(item.get("price", 0))
                        if price > 0:
                            result.setdefault(str(asset).upper(), []).append(ts)
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    continue
    except OSError:
        return {}
    # Duplicate timestamps must count as one Project60 sample.
    for asset, values in result.items():
        result[asset] = sorted(set(values))
    return result


def resolve_open_signals(
    path: str,
    current_price: float | dict,
    now: int | None = None,
    project60_path: str | None = None,
) -> int:
    """Resolve target/stop first, then expire forecasts after enough new samples."""
    p = Path(path)
    if not p.exists():
        return 0
    try:
        rows = [
            json.loads(line)
            for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError):
        return 0

    changed = 0
    now = int(time.time() if now is None else now)
    price_map = (
        {str(k).upper(): float(v) for k, v in current_price.items()}
        if isinstance(current_price, dict) else None
    )
    sample_times = _project60_sample_timestamps(project60_path)

    for row in rows:
        if row.get("status") != "OPEN":
            continue
        try:
            if price_map is not None:
                asset = str(row.get("asset", "")).upper()
                if asset not in price_map:
                    continue
                price = price_map[asset]
            else:
                price = float(current_price)

            direction = str(row["direction"]).upper()
            entry = float(row["entry_price"])
            stop = float(row["stop"])
            target = float(row["target"])
            status = resolve_signal(entry, price, direction, stop, target)
        except (KeyError, TypeError, ValueError):
            continue

        bars_elapsed = None
        horizon = None
        if status == "OPEN" and sample_times:
            try:
                horizon = int(row.get("horizon_bars") or 0)
                forecast_ts = int(row["forecast_ts"])
                asset = str(row.get("asset", "")).upper()
                times = sample_times.get(asset, [])
                bars_elapsed = len(times) - bisect_right(times, forecast_ts)
            except (KeyError, TypeError, ValueError):
                bars_elapsed = None

            if (
                horizon is not None and horizon > 0
                and bars_elapsed is not None and bars_elapsed >= horizon
            ):
                status = "EXPIRED"

        if status == "OPEN":
            continue

        if status == "TARGET":
            exit_price = target
        elif status == "STOP":
            exit_price = stop
        else:
            exit_price = price

        gross_pct = (
            (exit_price - entry) / entry * 100
            if direction == "BULLISH"
            else (entry - exit_price) / entry * 100
        )
        cost_pct = float(row.get("round_trip_cost_pct", 0.0) or 0.0)
        capital = float(row.get("capital_usd", 500.0) or 500.0)
        row.update({
            "status": status,
            "resolved_ts": now,
            "exit_price": exit_price,
            "observed_price": price,
            "exit_price_model": (
                "time_exit_observed_price"
                if status == "EXPIRED"
                else "stop_target_level_simulation"
            ),
            "gross_move_pct": round(gross_pct, 6),
            "net_profit_usd": round(capital * (gross_pct - cost_pct) / 100, 4),
        })
        if status == "EXPIRED":
            row["expiry_reason"] = "forecast_horizon_elapsed"
            row["bars_elapsed"] = bars_elapsed
            row["horizon_bars"] = horizon
        changed += 1

    if changed:
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        tmp.replace(p)
    return changed

def _bucket_confidence(value):
    try:
        x=float(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if x < 0.60:
        return "LOW"
    if x < 0.75:
        return "MEDIUM"
    if x < 0.90:
        return "HIGH"
    return "VERY_HIGH"


def _bucket_economic(value):
    try:
        x=float(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if x >= 10.0:
        return "PREFERRED"
    if x >= 4.0:
        return "ACCEPTABLE"
    return "BELOW_MIN"


def _group_outcomes(rows, key_fn):
    groups = {}
    for row in rows:
        key = key_fn(row)
        item = groups.setdefault(key, {
            "resolved": 0, "closed": 0, "expired": 0,
            "wins": 0, "losses": 0, "net_profit_usd": 0.0,
        })
        item["closed"] += 1
        status = row.get("status")
        if status in ("TARGET", "STOP"):
            item["resolved"] += 1
        elif status == "EXPIRED":
            item["expired"] += 1
        if status == "TARGET":
            item["wins"] += 1
        elif status == "STOP":
            item["losses"] += 1
        item["net_profit_usd"] += float(row.get("net_profit_usd", 0.0) or 0.0)
    for item in groups.values():
        n = item["resolved"]
        item["win_rate"] = round(item["wins"] / n, 4) if n else 0.0
        item["net_profit_usd"] = round(item["net_profit_usd"], 4)
    return groups


def summarize(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {
            "count": 0, "open": 0, "resolved": 0, "closed": 0, "expired": 0,
            "wins": 0, "losses": 0, "win_rate": 0.0, "net_profit_usd": 0.0,
            "by_regime": {}, "by_direction": {},
            "by_confidence": {}, "by_economic_tier": {},
        }

    rows = []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    resolved = [r for r in rows if r.get("status") in ("TARGET", "STOP")]
    closed = [r for r in rows if r.get("status") in ("TARGET", "STOP", "EXPIRED")]
    expired = [r for r in rows if r.get("status") == "EXPIRED"]
    wins = sum(r.get("status") == "TARGET" for r in resolved)
    losses = sum(r.get("status") == "STOP" for r in resolved)
    net = sum(float(r.get("net_profit_usd", 0.0) or 0.0) for r in closed)

    return {
        "count": len(rows),
        "open": sum(r.get("status") == "OPEN" for r in rows),
        "resolved": len(resolved),
        "closed": len(closed),
        "expired": len(expired),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(resolved), 4) if resolved else 0.0,
        "net_profit_usd": round(net, 4),
        "by_regime": _group_outcomes(
            closed, lambda r: str(r.get("regime", "UNKNOWN")).upper() or "UNKNOWN"
        ),
        "by_direction": _group_outcomes(
            closed, lambda r: str(r.get("direction", "UNKNOWN")).upper() or "UNKNOWN"
        ),
        "by_confidence": _group_outcomes(
            closed, lambda r: _bucket_confidence(r.get("confidence"))
        ),
        "by_economic_tier": _group_outcomes(
            closed, lambda r: _bucket_economic(r.get("modeled_profit_usd"))
        ),
    }
