import unittest

from mi_core.hyperliquid_data import PerpCandle, FundingEvent
from mi_core.regime_wfa import calculate_regime, dynamic_levels, _simulate_exit


def candle(i, o, h, l, c):
    return PerpCandle("BTC", i * 3_600_000, (i + 1) * 3_600_000 - 1,
                      o, h, l, c, 10.0, 1)


class RegimeWfaTests(unittest.TestCase):
    def test_atr_adx_are_causal_and_regime_fields_present(self):
        rows = [candle(i, 100+i, 102+i, 99+i, 101+i) for i in range(150)]
        out = calculate_regime(rows, period=14, volatility_window=100)
        self.assertEqual(len(out), len(rows))
        self.assertIsNone(out[0]["atr"])
        self.assertIsNotNone(out[-1]["atr"])
        self.assertIsNotNone(out[-1]["adx"])
        self.assertIn("regime_ok", out[-1])

    def test_atr_adx_rejects_invalid_periods(self):
        with self.assertRaises(ValueError):
            calculate_regime([candle(0,100,101,99,100)], period=1)
        with self.assertRaises(ValueError):
            calculate_regime([candle(0,100,101,99,100)], volatility_window=10)

    def test_dynamic_levels_long_and_short_are_ordered(self):
        rows = [candle(i, 100, 103, 98, 101) for i in range(25)]
        long = dynamic_levels(rows, 24, 101, 1, 2.0)
        short = dynamic_levels(rows, 24, 101, -1, 2.0)
        self.assertLess(long["stop"], 101)
        self.assertGreater(long["target"], 101)
        self.assertGreater(short["stop"], 101)
        self.assertLess(short["target"], 101)
        self.assertEqual(long["support"], 98)
        self.assertEqual(long["resistance"], 103)

    def test_stop_wins_same_candle_stop_target_ambiguity(self):
        rows = [candle(0, 100, 112, 88, 100)]
        out = _simulate_exit(rows, 0, 1, 90, 110, 1)
        self.assertEqual(out["exit_reason"], "STOP")
        self.assertTrue(out["same_bar_ambiguity"])
        self.assertEqual(out["exit_price"], 90)

    def test_target_exit_and_time_exit(self):
        target_rows = [candle(0, 100, 111, 95, 108)]
        target = _simulate_exit(target_rows, 0, 1, 90, 110, 1)
        self.assertEqual(target["exit_reason"], "TARGET")
        time_rows = [candle(0, 100, 105, 95, 102), candle(1,102,106,96,104)]
        timed = _simulate_exit(time_rows, 0, 1, 90, 110, 2)
        self.assertEqual(timed["exit_reason"], "TIME")
        self.assertEqual(timed["exit_price"], 104)

    def test_no_future_bars_used_for_dynamic_levels(self):
        rows = [candle(i, 100, 103, 98, 101) for i in range(30)]
        first = dynamic_levels(rows, 19, 101, 1, 2.0)
        rows[20] = candle(20, 100, 1000, 1, 500)
        second = dynamic_levels(rows, 19, 101, 1, 2.0)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
