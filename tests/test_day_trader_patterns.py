import unittest

from mi_core.day_trader_patterns import scan_day_trader_patterns


class DayTraderPatternTests(unittest.TestCase):
    def test_detects_close_breakout_without_using_current_bar_in_reference(self):
        result = scan_day_trader_patterns(list(range(1, 22)))
        self.assertTrue(result["patterns"]["breakout_20d"])
        self.assertIn("breakout_20d", result["active_candidates"])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

    def test_breakout_is_false_when_latest_close_does_not_exceed_prior_closes(self):
        result = scan_day_trader_patterns(list(range(1, 21)) + [19.5])
        self.assertFalse(result["patterns"]["breakout_20d"])

    def test_detects_bull_flag_after_impulse_and_tight_consolidation(self):
        closes = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 115,
                  114, 113, 112, 114, 113]
        result = scan_day_trader_patterns(closes)
        self.assertTrue(result["patterns"]["bull_flag"])

    def test_detects_moving_average_reclaim(self):
        closes = [100.0] * 19 + [90.0, 110.0]
        result = scan_day_trader_patterns(closes)
        self.assertTrue(result["patterns"]["reclaim_ma20"])

    def test_detects_oversold_rsi_in_declining_market(self):
        closes = [100.0 - i for i in range(20)]
        result = scan_day_trader_patterns(closes)
        self.assertTrue(result["patterns"]["rsi_oversold"])
        self.assertEqual(result["rsi_value"], 0.0)

    def test_insufficient_history_is_unknown_not_false(self):
        result = scan_day_trader_patterns([100, 101, 102])
        self.assertIsNone(result["patterns"]["breakout_20d"])
        self.assertIsNone(result["patterns"]["rsi_oversold"])
        self.assertEqual(result["active_candidates"], [])

    def test_rejects_non_finite_or_non_positive_closes(self):
        for invalid in ([100, float("nan")], [100, float("inf")], [100, 0]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    scan_day_trader_patterns(invalid)

    def test_rejects_invalid_parameters(self):
        with self.assertRaises(ValueError):
            scan_day_trader_patterns([100, 101, 102], breakout_lookback=1)
        with self.assertRaises(ValueError):
            scan_day_trader_patterns([100, 101, 102], rsi_oversold=100)


if __name__ == "__main__":
    unittest.main()
