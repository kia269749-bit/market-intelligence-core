import unittest

from mi_core.real_data import rows_to_bars

class RealDataTests(unittest.TestCase):
    def test_kline_mapping_uses_close_and_taker_buy_volume(self):
        rows = [[1700000000000, "1", "2", "0.5", "1.5", "100", 0, "0", 10, "60", "0", "0"]]
        bars = rows_to_bars(rows, "BTCUSDT")
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].price, 1.5)
        self.assertEqual(bars[0].open, 1.0)
        self.assertEqual(bars[0].high, 2.0)
        self.assertEqual(bars[0].low, 0.5)
        self.assertEqual(bars[0].buy_volume, 60.0)
        self.assertEqual(bars[0].sell_volume, 40.0)

    def test_empty_rows(self):
        self.assertEqual(rows_to_bars([], "BTCUSDT"), [])

if __name__ == "__main__":
    unittest.main()
