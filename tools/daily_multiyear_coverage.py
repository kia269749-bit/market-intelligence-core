"""Audit multi-year daily OHLC coverage for a current liquid-crypto universe.

This is a data inventory only. It does not rank strategies or place orders.
Current-universe selection has survivorship bias by design; delisted assets are not
silently represented as present.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.real_data import download as download_real

UNIVERSE = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT",
    "BCHUSDT", "LTCUSDT", "DOTUSDT", "UNIUSDT", "ETCUSDT",
    "NEARUSDT", "ATOMUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    "FILUSDT", "ICPUSDT", "INJUSDT", "SUIUSDT", "SEIUSDT",
    "TIAUSDT", "SHIBUSDT", "RENDERUSDT", "PEPEUSDT", "AAVEUSDT",
)
DAY_MS = 86_400_000
FIVE_YEARS_DAYS = 365 * 5


def summarize_coverage(symbol: str, bars: list, now_ms: int | None = None) -> dict:
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    if not bars:
        return {
            "symbol": symbol, "status": "no_data", "raw_rows": 0,
            "usable_complete_daily_rows": 0, "first_date_utc": None,
            "last_complete_date_utc": None, "history_days": 0,
            "missing_daily_bars_estimate": None, "gap_count": None,
            "five_year_history_available": False,
        }
    ordered = sorted({int(b.ts): b for b in bars}.values(), key=lambda b: int(b.ts))
    timestamps = [int(b.ts) for b in ordered]
    current_day_open = (now_ms // DAY_MS) * DAY_MS
    complete = [b for b in ordered if int(b.ts) < current_day_open]
    complete_ts = [int(b.ts) for b in complete]
    first_ts = timestamps[0]
    last_complete_ts = complete_ts[-1] if complete_ts else None
    expected = ((last_complete_ts - first_ts) // DAY_MS + 1) if last_complete_ts is not None else 0
    gaps = []
    for left, right in zip(complete_ts, complete_ts[1:]):
        delta = right - left
        if delta > DAY_MS:
            gaps.append({
                "after_date_utc": datetime.fromtimestamp(left / 1000, timezone.utc).date().isoformat(),
                "before_date_utc": datetime.fromtimestamp(right / 1000, timezone.utc).date().isoformat(),
                "missing_days": max(0, delta // DAY_MS - 1),
            })
    return {
        "symbol": symbol,
        "status": "ok" if complete else "no_complete_daily_bars",
        "raw_rows": len(ordered),
        "usable_complete_daily_rows": len(complete),
        "first_date_utc": datetime.fromtimestamp(first_ts / 1000, timezone.utc).date().isoformat(),
        "last_complete_date_utc": (
            datetime.fromtimestamp(last_complete_ts / 1000, timezone.utc).date().isoformat()
            if last_complete_ts is not None else None
        ),
        "history_days": expected,
        "missing_daily_bars_estimate": max(0, expected - len(complete)),
        "gap_count": len(gaps),
        "gaps": gaps[:100],
        "five_year_history_available": expected >= FIVE_YEARS_DAYS,
        "current_utc_day_candle_excluded": len(ordered) > len(complete),
    }


def build_report(rows: list[dict], requested_bars: int = 2200) -> dict:
    good = [r for r in rows if r.get("status") == "ok"]
    return {
        "status": "ok" if good else "no_data",
        "venue": "Binance public spot klines API",
        "interval": "1d",
        "requested_daily_bars_per_symbol": requested_bars,
        "universe": list(UNIVERSE),
        "requested_symbol_count": len(UNIVERSE),
        "symbols_with_data": len(good),
        "symbols_with_at_least_five_years": sum(bool(r.get("five_year_history_available")) for r in good),
        "symbols": rows,
        "research_only": True,
        "live_orders": False,
        "survivorship_bias": (
            "Survivorship bias is material. Universe is selected from currently listed liquid USDT spot pairs. "
            "Delisted, failed, renamed, or historically illiquid assets are not fully represented; "
            "this coverage audit does not remove that bias."
        ),
        "execution_cost_limitation": (
            "Daily OHLC candles do not contain historical bid-ask spread or realized slippage. "
            "Those must be modeled as explicit conservative scenarios later, not claimed as observed."
        ),
        "holdout_policy": (
            "This step only audits data. No strategy is fitted and no final holdout is examined. "
            "Before strategy research, freeze a timestamp-based final 20% boundary in a separate report."
        ),
    }


def run(out_dir: Path, report_path: Path, requested_bars: int = 2200) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for symbol in UNIVERSE:
        target = out_dir / f"{symbol}_1d.jsonl"
        try:
            bars, path = download_real(
                symbol=symbol, interval="1d", bars=requested_bars,
                out=str(target), sleep_s=0.15,
            )
            row = summarize_coverage(symbol, bars)
            row["data_path"] = str(path)
            rows.append(row)
            print(json.dumps({
                "symbol": symbol, "status": row["status"],
                "usable_complete_daily_rows": row["usable_complete_daily_rows"],
                "first_date_utc": row["first_date_utc"],
                "last_complete_date_utc": row["last_complete_date_utc"],
                "history_days": row["history_days"],
                "gap_count": row["gap_count"],
            }, sort_keys=True))
        except Exception as exc:
            row = {
                "symbol": symbol, "status": "fetch_error", "raw_rows": 0,
                "usable_complete_daily_rows": 0, "first_date_utc": None,
                "last_complete_date_utc": None, "history_days": 0,
                "missing_daily_bars_estimate": None, "gap_count": None,
                "five_year_history_available": False,
                "error": f"{type(exc).__name__}: {exc}",
                "data_path": str(target),
            }
            rows.append(row)
            print(json.dumps(row, sort_keys=True))
    report = build_report(rows, requested_bars=requested_bars)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "report": str(report_path),
        "status": report["status"],
        "requested_symbol_count": report["requested_symbol_count"],
        "symbols_with_data": report["symbols_with_data"],
        "symbols_with_at_least_five_years": report["symbols_with_at_least_five_years"],
        "research_only": True, "live_orders": False,
    }, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="data/daily_multiyear")
    parser.add_argument("--report", default="reports/daily_multiyear_coverage.json")
    parser.add_argument("--bars", type=int, default=2200)
    args = parser.parse_args()
    if args.bars < 1825:
        parser.error("--bars must be at least 1825 to attempt five years of daily history")
    run(Path(args.out_dir), Path(args.report), requested_bars=args.bars)


if __name__ == "__main__":
    main()
