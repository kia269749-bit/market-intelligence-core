import unittest

from mi_core.day_trader_orb import run_opening_range_breakout


def bar(session, ts, o, h, l, c):
    return {"session": session, "timestamp": ts, "open": o, "high": h, "low": l, "close": c}


class DayTraderOrbTests(unittest.TestCase):
    def test_breakout_target_and_central_cost_model(self):
        bars = [
            bar("s1", "2026-01-01T00:00:00Z", 100, 101, 99, 100),
            bar("s1", "2026-01-01T00:05:00Z", 100, 102, 99, 101),
            bar("s1", "2026-01-01T00:10:00Z", 101, 101.5, 98, 100),
            bar("s1", "2026-01-01T00:15:00Z", 102, 104, 101, 103),
            bar("s1", "2026-01-01T00:20:00Z", 103, 106, 102, 105),
        ]
        result = run_opening_range_breakout(
            bars, opening_range_bars=3, target_r=1.0, capital_usd=500,
            position_fraction=0.25,
        )
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["trades_count"], 1)
        self.assertEqual(result["trades"][0]["outcome"], "target")
        self.assertAlmostEqual(result["round_trip_cost_bps"], 24.0)
        self.assertAlmostEqual(result["trades"][0]["round_trip_cost_pct"], 0.24)
        self.assertAlmostEqual(result["trades"][0]["net_pnl_usd"], 3.34, places=2)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

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

    def test_invalid_ohlc_is_rejected(self):
        with self.assertRaises(ValueError):
            run_opening_range_breakout([bar("s1", "1", 100, 98, 99, 100)])


if __name__ == "__main__":
    unittest.main()
