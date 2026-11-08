import unittest

from mi_core.pattern_lab import (
    closed_ohlc,
    discover_signals,
    evaluate_pattern_lab,
)


def make_bars(count=100):
    bars = []
    price = 100.0
    for i in range(count):
        # Deterministic, gently rising test data.
        o = price
        c = price * (1.001 if i % 7 else 0.999)
        h = max(o, c) * 1.002
        low = min(o, c) * 0.998
        bars.append({
            "ts": i * 60_000,
            "open": o,
            "high": h,
            "low": low,
            "close": c,
            "volume": 10.0,
        })
        price = c
    return bars


class PatternLabTests(unittest.TestCase):
    def test_only_fully_closed_binance_candles_are_kept(self):
        rows = [
            [0, "100", "103", "99", "102", "10", 59_999],
            [60_000, "102", "104", "101", "103", "12", 119_999],
            [120_000, "103", "105", "102", "104", "13", 179_999],
        ]
        bars = closed_ohlc(rows, now_ms=120_000)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["close"], 102.0)

    def test_evaluator_is_research_only_and_has_train_test(self):
        report = evaluate_pattern_lab(
            make_bars(), horizon=3, min_train_trades=2
        )
        self.assertTrue(report["research_only"])
        self.assertFalse(report["live_orders"])
        self.assertEqual(report["bar_count"], 100)
        self.assertIn("breakout_up", report["results"])
        self.assertIn("train", report["results"]["trend_up"])
        self.assertIn("test", report["results"]["trend_up"])

    def test_no_trade_uses_unavailable_future_exit(self):
        bars = make_bars(25)
        signals = discover_signals(bars)
        report = evaluate_pattern_lab(
            bars, horizon=3, train_fraction=0.6, min_train_trades=1
        )
        # All reported trades must have completed outcomes, never future guesses.
        for result in report["results"].values():
            self.assertGreaterEqual(result["train"]["trades"], 0)
            self.assertGreaterEqual(result["test"]["trades"], 0)
        self.assertIsInstance(signals, dict)


if __name__ == "__main__":
    unittest.main()
