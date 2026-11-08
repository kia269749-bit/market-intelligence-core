import unittest
from mi_core.timing_engine import evaluate_entry_timing, evaluate_exit_timing


class TimingEngineTests(unittest.TestCase):
    def test_early_entry_is_detected(self):
        r = evaluate_entry_timing(
            confidence=.82, expected_move_pct=3.0, current_move_pct=.4,
            required_move_pct=1.15, agreement=.85, quality_score=1.0,
            regime="TREND",
        )
        self.assertEqual(r["state"], "EARLY")

    def test_entry_becomes_late(self):
        r = evaluate_entry_timing(
            confidence=.90, expected_move_pct=3.0, current_move_pct=2.4,
            required_move_pct=1.15, agreement=.85, quality_score=1.0,
            regime="TREND",
        )
        self.assertEqual(r["state"], "LATE")

    def test_two_exit_warnings_take_profit(self):
        r = evaluate_exit_timing(
            position_open=True, profit_pct=1.8,
            leader_exit=True, orderbook_deterioration=True,
        )
        self.assertEqual(r["state"], "TAKE_PROFIT")

    def test_multiple_exit_warnings_exit(self):
        r = evaluate_exit_timing(
            position_open=True, profit_pct=2.2, momentum_score=-.5,
            leader_exit=True, orderbook_deterioration=True,
            tradeflow_deterioration=True, forecast_reversal=True,
        )
        self.assertEqual(r["state"], "EXIT")

    def test_current_move_is_exposed_in_timing(self):
        r = evaluate_entry_timing(
            confidence=.82, expected_move_pct=3.0, current_move_pct=.4,
            required_move_pct=1.15, agreement=.85, quality_score=1.0,
            regime="TREND",
        )
        self.assertAlmostEqual(r["remaining_move_pct"], 2.6, places=4)

    def test_no_position(self):
        self.assertEqual(
            evaluate_exit_timing(position_open=False)["state"], "NO_POSITION"
        )

    def test_entry_rejects_non_finite_values(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                r = evaluate_entry_timing(expected_move_pct=value)
                self.assertEqual(r["state"], "WAIT")
                self.assertEqual(r["reason"], "invalid_input")
                self.assertTrue(r["research_only"])
                self.assertFalse(r["live_orders"])

    def test_entry_rejects_invalid_confidence_ranges(self):
        for field in ("confidence", "agreement", "quality_score"):
            for value in (-0.01, 1.01):
                with self.subTest(field=field, value=value):
                    r = evaluate_entry_timing(**{field: value})
                    self.assertEqual(r["reason"], "invalid_input")

    def test_entry_rejects_non_numeric_values(self):
        r = evaluate_entry_timing(expected_move_pct="not-a-number")
        self.assertEqual(r["state"], "WAIT")
        self.assertEqual(r["reason"], "invalid_input")

    def test_exit_rejects_non_finite_values(self):
        for field in ("profit_pct", "momentum_score", "remaining_move_pct"):
            r = evaluate_exit_timing(**{field: float("nan")})
            with self.subTest(field=field):
                self.assertEqual(r["state"], "WAIT")
                self.assertEqual(r["reason"], "invalid_input")
                self.assertTrue(r["research_only"])
                self.assertFalse(r["live_orders"])


if __name__ == "__main__":
    unittest.main()
