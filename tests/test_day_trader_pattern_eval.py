import unittest

from mi_core.day_trader_pattern_eval import evaluate_day_trader_patterns


def rising_bars(count=60):
    bars = []
    for i in range(count):
        close = 100.0 + i * 0.4
        bars.append({
            "timestamp": i,
            "open": close - 0.1,
            "close": close,
        })
    return bars


class DayTraderPatternEvaluationTests(unittest.TestCase):
    def test_runs_pattern_event_study_and_marks_research_only(self):
        result = evaluate_day_trader_patterns(rising_bars(), horizon_bars=3)
        self.assertEqual(result["status"], "OK")
        self.assertGreater(result["eligible_signal_bars"], 0)
        self.assertIn("breakout_20d", result["strategies"])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertIn("1.0", result["strategies"]["breakout_20d"]["stress"])

    def test_cost_stress_reduces_net_returns(self):
        result = evaluate_day_trader_patterns(rising_bars(), horizon_bars=3)
        stress = result["strategies"]["breakout_20d"]["stress"]
        self.assertEqual(stress["1.0"]["round_trip_cost_pct"], 0.24)
        self.assertEqual(stress["1.5"]["round_trip_cost_pct"], 0.36)
        self.assertEqual(stress["2.0"]["round_trip_cost_pct"], 0.48)
        self.assertGreater(
            stress["1.0"]["mean_net_return_pct"],
            stress["1.5"]["mean_net_return_pct"],
        )
        self.assertGreater(
            stress["1.5"]["mean_net_return_pct"],
            stress["2.0"]["mean_net_return_pct"],
        )

    def test_insufficient_history_is_reported(self):
        result = evaluate_day_trader_patterns(rising_bars(15), horizon_bars=3)
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertEqual(result["strategies"], {})

    def test_rejects_bad_prices_and_out_of_order_timestamps(self):
        bars = rising_bars()
        bars[10]["close"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite and positive"):
            evaluate_day_trader_patterns(bars)

        bars = rising_bars()
        bars[10]["timestamp"] = 2
        with self.assertRaisesRegex(ValueError, "chronological"):
            evaluate_day_trader_patterns(bars)

    def test_rejects_invalid_horizon_and_cost_multiplier(self):
        with self.assertRaisesRegex(ValueError, "horizon_bars"):
            evaluate_day_trader_patterns(rising_bars(), horizon_bars=0)
        with self.assertRaisesRegex(ValueError, "cost multipliers"):
            evaluate_day_trader_patterns(rising_bars(), cost_multipliers=(1.0, float("nan")))


if __name__ == "__main__":
    unittest.main()
