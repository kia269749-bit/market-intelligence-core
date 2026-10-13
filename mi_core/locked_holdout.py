"""Chronological dataset gate: development and final holdout are separate files/modes."""
from __future__ import annotations
import csv
import json
from datetime import date
from pathlib import Path

LOCK_PATH = Path(__file__).resolve().parents[1] / "config" / "final_holdout_lock.json"

def read_lock(path=LOCK_PATH):
    with open(path, encoding="utf-8") as f:
        lock = json.load(f)
    start = date.fromisoformat(lock["dataset_start"])
    dev_end = date.fromisoformat(lock["development_end_inclusive"])
    holdout_start = date.fromisoformat(lock["final_holdout_start"])
    end = date.fromisoformat(lock["final_holdout_end_inclusive"])
    if not (start <= dev_end < holdout_start <= end):
        raise ValueError("invalid chronological holdout lock")
    return lock

def load_rows(path, *, step="development", lock_path=LOCK_PATH):
    """Load exactly one partition file.

    Development mode opens only a development-partition file and rejects any
    row beyond development_end_inclusive. Final holdout rows require a separate
    explicit call with step='final-step' and a path to the holdout partition.
    No single-file scan crosses the boundary.
    """
    if step not in ("development", "final-step"):
        raise ValueError("step must be 'development' or explicit 'final-step'")
    lock = read_lock(lock_path)
    start = date.fromisoformat(lock["dataset_start"])
    dev_end = date.fromisoformat(lock["development_end_inclusive"])
    holdout_start = date.fromisoformat(lock["final_holdout_start"])
    end = date.fromisoformat(lock["final_holdout_end_inclusive"])
    lower, upper = (start, dev_end) if step == "development" else (holdout_start, end)
    result = []
    previous = None
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "date" not in reader.fieldnames:
            raise ValueError("CSV requires a 'date' column")
        for row in reader:
            current = date.fromisoformat(row["date"][:10])
            if previous is not None and current < previous:
                raise ValueError("input CSV must be sorted by date ascending")
            previous = current
            if not lower <= current <= upper:
                raise ValueError(f"{step} partition contains out-of-range date: {current.isoformat()}")
            result.append(row)
    return result

def availability_counts(coverage_rows, *, start="2020-10-05", end="2026-10-12"):
    """Return year/month symbol counts from rows with symbol/start_date/end_date."""
    from collections import defaultdict
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    yearly, monthly = defaultdict(set), defaultdict(set)
    for item in coverage_rows:
        symbol = item["symbol"]
        a = max(first, date.fromisoformat(item["start_date"][:10]))
        b = min(last, date.fromisoformat(item["end_date"][:10]))
        if b < a:
            continue
        cursor = date(a.year, a.month, 1)
        while cursor <= b:
            monthly[cursor.isoformat()[:7]].add(symbol)
            cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        for year in range(a.year, b.year + 1):
            yearly[str(year)].add(symbol)
    return (
        {k: len(v) for k, v in sorted(yearly.items())},
        {k: len(v) for k, v in sorted(monthly.items())},
    )
