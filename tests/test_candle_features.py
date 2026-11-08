import unittest
from mi_core.models import MarketBar
from mi_core.candle_features import true_range, atr_series, candle_shape


def bar(i, o, h, l, c):
    return MarketBar(ts=i, symbol="X", price=c, open=o, high=h, low=l)


class CandleFeaturesTest(unittest.TestCase):
    def test_shape_known_values(self):
        s = candle_shape(bar(0, 100, 110, 90, 105))
        self.assertAlmostEqual(s["body"], 0.25)
        self.assertAlmostEqual(s["upper_wick"], 0.25)
        self.assertAlmostEqual(s["lower_wick"], 0.5)
        self.assertEqual(s["direction"], 1)

    def test_shape_missing_or_flat(self):
        self.assertIsNone(candle_shape(MarketBar(ts=0, symbol="X", price=1.0)))
        self.assertIsNone(candle_shape(bar(0, 5, 5, 5, 5)))

    def test_true_range_uses_gap(self):
        self.assertEqual(true_range(bar(1, 100, 101, 99, 100), 90), 11)

    def test_atr_constant_range(self):
        bars = [bar(i, 100, 101, 99, 100) for i in range(6)]
        a = atr_series(bars, 3)
        self.assertEqual(a[:2], [None, None])
        self.assertAlmostEqual(a[2], 2.0)
        self.assertAlmostEqual(a[5], 2.0)

    def test_no_lookahead(self):
        bars = [bar(i, 100, 101 + i % 3, 99, 100 + i % 2) for i in range(12)]
        base = atr_series(bars, 3)
        changed = bars[:8] + [bar(8, 100, 500, 1, 100)] + bars[9:]
        alt = atr_series(changed, 3)
        self.assertEqual(base[:8], alt[:8])

    def test_missing_ohlc_resets(self):
        bars = [bar(i, 100, 101, 99, 100) for i in range(4)]
        bars.append(MarketBar(ts=4, symbol="X", price=100.0))
        bars += [bar(i, 100, 101, 99, 100) for i in range(5, 8)]
        a = atr_series(bars, 3)
        self.assertIsNotNone(a[3])
        self.assertIsNone(a[4])
        self.assertIsNone(a[6])
        self.assertIsNotNone(a[7])


if __name__ == "__main__":
    unittest.main()
