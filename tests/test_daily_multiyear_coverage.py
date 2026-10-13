import unittest
from types import SimpleNamespace

from tools.daily_multiyear_coverage import DAY_MS, build_report, summarize_coverage, UNIVERSE


class DailyCoverageTests(unittest.TestCase):
    def test_current_day_is_excluded_and_gaps_are_reported(self):
        bars = [
            SimpleNamespace(ts=0),
            SimpleNamespace(ts=DAY_MS),
            SimpleNamespace(ts=3 * DAY_MS),
            SimpleNamespace(ts=4 * DAY_MS),
        ]
        row = summarize_coverage("TESTUSDT", bars, now_ms=4 * DAY_MS + 1000)
        self.assertEqual(row["usable_complete_daily_rows"], 3)
        self.assertEqual(row["first_date_utc"], "1970-01-01")
        self.assertEqual(row["last_complete_date_utc"], "1970-01-04")
        self.assertEqual(row["gap_count"], 1)
        self.assertEqual(row["missing_daily_bars_estimate"], 1)
        self.assertTrue(row["current_utc_day_candle_excluded"])

    def test_empty_history_is_explicit(self):
        row = summarize_coverage("EMPTYUSDT", [], now_ms=0)
        self.assertEqual(row["status"], "no_data")
        self.assertFalse(row["five_year_history_available"])

    def test_report_marks_survivorship_and_research_only(self):
        report = build_report([summarize_coverage("TESTUSDT", [], now_ms=0)])
        self.assertEqual(len(UNIVERSE), 30)
        self.assertTrue(report["research_only"])
        self.assertFalse(report["live_orders"])
        self.assertIn("Survivorship", report["survivorship_bias"])
        self.assertIn("historical bid-ask spread", report["execution_cost_limitation"])

    def test_five_year_flag_uses_complete_history_span(self):
        bars = [SimpleNamespace(ts=i * DAY_MS) for i in range(1826)]
        row = summarize_coverage("LONGUSDT", bars, now_ms=1826 * DAY_MS + 1)
        self.assertTrue(row["five_year_history_available"])
        self.assertEqual(row["history_days"], 1826)


if __name__ == "__main__":
    unittest.main()
