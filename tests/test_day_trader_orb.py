import unittest

from mi_core.day_trader_orb import run_opening_range_breakout


def bar(session, ts, o, h, l, c):
    return {"session": session, "timestamp": ts, "open": o, "high": h, "low": l, "close": c}


def winning_fixture():
    return [
        bar("s1", "2026-01-01T00:00:00Z", 100, 101, 99, 100),
        bar("s1", "2026-01-01T00:05:00Z", 100, 102, 99, 101),
        bar("s1", "2026-01-01T00:10:00Z", 101, 101.5, 98, 100),
        bar("s1", "2026-01-01T00:15:00Z", 102, 104, 101, 103),
        bar("s1", "2026-01-01T00:20:00Z", 103, 106, 102, 105),
    ]


class DayTraderOrbTests(unittest.TestCase):
    def test_breakout_target_and_central_cost_model(self):
        result = run_opening_range_breakout(
            winning_fixture(), opening_range_bars=3, target_r=1.0,
            capital_usd=500, position_fraction=0.25,
        )
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["trades_count"], 1)
        self.assertEqual(result["trades"][0]["outcome"], "target")
        self.assertAlmostEqual(result["round_trip_cost_bps"], 24.0)
        self.assertAlmostEqual(result["trades"][0]["round_trip_cost_pct"], 0.24)
        self.assertAlmostEqual(result["trades"][0]["net_pnl_usd"], 3.34, places=2)
        self.assertAlmostEqual(result["risk_budget_usd"], 5.0)
        self.assertLessEqual(result["trades"][0]["notional_usd"], 125.0)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

    def test_cost_stress_reprices_same_setup_without_changing_central_config(self):
        base = run_opening_range_breakout(winning_fixture(), capital_usd=500)
        stress15 = run_opening_range_breakout(winning_fixture(), capital_usd=500, cost_multiplier=1.5)
        stress2 = run_opening_range_breakout(winning_fixture(), capital_usd=500, cost_multiplier=2.0)
        self.assertAlmostEqual(base["round_trip_cost_bps"], 24.0)
        self.assertAlmostEqual(stress15["round_trip_cost_bps"], 36.0)
        self.assertAlmostEqual(stress2["round_trip_cost_bps"], 48.0)
        self.assertGreater(base["net_profit_usd"], stress15["net_profit_usd"])
        self.assertGreater(stress15["net_profit_usd"], stress2["net_profit_usd"])

    def test_same_bar_stop_and_target_is_conservatively_stop_first(self):
        bars = [
            bar("s1", "1", 100, 101, 99, 100),
            bar("s1", "2", 100, 102, 99, 101),
            bar("s1", "3", 101, 101.5, 98, 100),
            bar("s1", "4", 103, 104, 102, 103),
            bar("s1", "5", 103, 110, 90, 104),
        ]
        result = run_opening_range_breakout(bars, opening_range_bars=3, capital_usd=500)
        self.assertEqual(result["trades"][0]["outcome"], "stop")
        self.assertLess(result["net_profit_usd"], 0)

    def test_no_breakout_produces_no_trade(self):
        bars = [
            bar("s1", "1", 100, 101, 99, 100),
            bar("s1", "2", 100, 102, 99, 101),
            bar("s1", "3", 101, 101.5, 98, 100),
            bar("s1", "4", 100, 102, 99, 101),
        ]
        result = run_opening_range_breakout(bars, opening_range_bars=3)
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertEqual(result["trades_count"], 0)

    def test_numeric_timestamps_compare_numerically_not_lexicographically(self):
        bars = winning_fixture()
        for row, stamp in zip(bars, [8, 9, 10, 11, 12]):
            row["timestamp"] = stamp
        result = run_opening_range_breakout(bars, capital_usd=500)
        self.assertEqual(result["status"], "OK")

    def test_out_of_order_numeric_timestamps_are_rejected(self):
        bars = winning_fixture()
        for row, stamp in zip(bars, [8, 10, 9, 11, 12]):
            row["timestamp"] = stamp
        with self.assertRaisesRegex(ValueError, "chronological"):
            run_opening_range_breakout(bars, capital_usd=500)

    def test_duplicate_timestamps_are_rejected(self):
        bars = winning_fixture()
        bars[2]["timestamp"] = bars[1]["timestamp"]
        with self.assertRaisesRegex(ValueError, "unique timestamps"):
            run_opening_range_breakout(bars, capital_usd=500)

    def test_malformed_timestamp_is_rejected(self):
        bars = winning_fixture()
        bars[2]["timestamp"] = "not-a-timestamp"
        with self.assertRaisesRegex(ValueError, "numeric or ISO-8601"):
            run_opening_range_breakout(bars, capital_usd=500)

    def test_position_sizing_includes_estimated_round_trip_cost_in_stop_risk(self):
        result = run_opening_range_breakout(
            winning_fixture(), capital_usd=10000, position_fraction=1.0,
            risk_fraction=0.01,
        )
        trade = result["trades"][0]
        self.assertLessEqual(trade["estimated_stop_loss_usd"], trade["risk_budget_usd"])
        self.assertGreater(trade["estimated_stop_loss_usd"], 0)

    def test_invalid_ohlc_is_rejected(self):
        with self.assertRaises(ValueError):
            run_opening_range_breakout([bar("s1", "1", 100, 98, 99, 100)])


if __name__ == "__main__":
    unittest.main()
