import csv
import json
import tempfile
import unittest
from pathlib import Path
from mi_core.locked_holdout import load_rows, read_lock, availability_counts

class LockedHoldoutTests(unittest.TestCase):
    def test_lock_has_shared_calendar_boundary_and_day_counts(self):
        lock = read_lock()
        self.assertEqual(lock["calendar_days_inclusive"], 2199)
        self.assertEqual(lock["development_days"], 1759)
        self.assertEqual(lock["final_holdout_days"], 440)
        self.assertEqual(lock["development_end_inclusive"], "2025-07-29")
        self.assertEqual(lock["final_holdout_start"], "2025-07-30")

    def test_development_stops_before_reading_holdout_rows(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sorted.csv"
            path.write_text(
                "date,symbol,close\n"
                "2025-07-29,BTCUSDT,100\n"
                "2025-07-30,ETHUSDT,200\n"
                "2026-10-12,POISON_SHOULD_NOT_BE_READ,999\n",
                encoding="utf-8",
            )
            rows = load_rows(path, step="development")
            self.assertEqual([r["symbol"] for r in rows], ["BTCUSDT"])
            self.assertNotIn("POISON_SHOULD_NOT_BE_READ", str(rows))

    def test_holdout_requires_explicit_final_step(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sorted.csv"
            path.write_text(
                "date,symbol,close\n"
                "2025-07-29,BTCUSDT,100\n"
                "2025-07-30,ETHUSDT,200\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_rows(path, step="final")
            self.assertEqual([r["symbol"] for r in load_rows(path, step="final-step")], ["ETHUSDT"])

    def test_availability_counts_year_and_month(self):
        yearly, monthly = availability_counts([
            {"symbol":"OLD", "start_date":"2020-10-05", "end_date":"2026-10-12"},
            {"symbol":"NEW", "start_date":"2024-02-01", "end_date":"2026-10-12"},
        ])
        self.assertEqual(yearly["2021"], 1)
        self.assertEqual(yearly["2024"], 2)
        self.assertEqual(monthly["2024-01"], 1)
        self.assertEqual(monthly["2024-02"], 2)

if __name__ == "__main__":
    unittest.main()
