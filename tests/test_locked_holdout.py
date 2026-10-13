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

    def test_development_opens_only_development_partition_and_rejects_leakage(self):
        with tempfile.TemporaryDirectory() as td:
            dev = Path(td) / "development.csv"
            dev.write_text("date,symbol,close\n2025-07-29,BTCUSDT,100\n", encoding="utf-8")
            rows = load_rows(dev, step="development")
            self.assertEqual([r["symbol"] for r in rows], ["BTCUSDT"])
            bad = Path(td) / "contaminated-development.csv"
            bad.write_text("date,symbol,close\n2025-07-30,POISON_SHOULD_NOT_BE_IN_DEV,999\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "out-of-range date: 2025-07-30"):
                load_rows(bad, step="development")

    def test_holdout_requires_explicit_final_step_and_separate_file(self):
        with tempfile.TemporaryDirectory() as td:
            final = Path(td) / "final_holdout.csv"
            final.write_text("date,symbol,close\n2025-07-30,ETHUSDT,200\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_rows(final, step="final")
            self.assertEqual([r["symbol"] for r in load_rows(final, step="final-step")], ["ETHUSDT"])

    def test_availability_counts_year_and_month(self):
        yearly, monthly = availability_counts([
            {"symbol":"OLD", "start_date":"2020-10-05", "end_date":"2026-10-12"},
            {"symbol":"NEW", "start_date":"2024-02-01", "end_date":"2026-10-12"},
        ])
        self.assertEqual(yearly["2021"], 1)
        self.assertEqual(yearly["2024"], 2)
        self.assertEqual(monthly["2024-01"], 1)
        self.assertEqual(monthly["2024-02"], 2)

    def test_final_holdout_file_is_not_wired_into_development_or_strategy_code(self):
        # The final dataset path must not be embedded in any production Python
        # module, and the explicit holdout loader must not be called by a
        # development/strategy module. Tests and the gate implementation are
        # excluded because they necessarily mention these APIs.
        root = Path(__file__).resolve().parents[1]
        forbidden = ("final_holdout.csv", "final_holdout.jsonl", "final_holdout.parquet")
        violations = []
        for source in root.rglob("*.py"):
            relative = source.relative_to(root)
            if relative.parts[0] in {"tests", ".git"}:
                continue
            if relative.as_posix() == "mi_core/locked_holdout.py":
                continue
            try:
                content = source.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            if any(token in content for token in forbidden):
                violations.append(f"{relative}: final holdout dataset path literal")
            if "load_rows(" in content or 'step="final-step"' in content or "step='final-step'" in content:
                violations.append(f"{relative}: direct locked-holdout loader/mode reference")
        self.assertEqual(violations, [], "final holdout wired into production code: " + "; ".join(violations))

if __name__ == "__main__":
    unittest.main()
