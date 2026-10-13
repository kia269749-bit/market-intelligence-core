"""Chronological dataset gate: development and final holdout are separate modes."""
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
    """Read sorted CSV rows. Development stops at the first holdout timestamp.

    The final segment is deliberately unavailable unless step='final-step' is
    passed explicitly. Input must be sorted by timestamp ascending.
    """
    if step not in ("development", "final-step"):
        raise ValueError("step must be 'development' or explicit 'final-step'")
    lock = read_lock(lock_path)
    start = date.fromisoformat(lock["dataset_start"])
    dev_end = date.fromisoformat(lock["development_end_inclusive"])
    holdout_start = date.fromisoformat(lock["final_holdout_start"])
    end = date.fromisoformat(lock["final_holdout_end_inclusive"])
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
            if step == "development" and current >= holdout_start:
                break
            if step == "final-step":
                if current < holdout_start:
                    continue
                if current > end:
                    break
                result.append(row)
            elif start <= current <= dev_end:
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
