import unittest
from unittest.mock import patch

from mi_core.multi_exchange import DEFAULT_SYMBOLS, EXCHANGES, fetch_snapshot


class MultiExchangeCompatibilityTests(unittest.TestCase):
    def test_default_universe(self):
        self.assertGreaterEqual(len(DEFAULT_SYMBOLS), 10)
        self.assertIn("BTCUSDT", DEFAULT_SYMBOLS)
        self.assertIn("ETHUSDT", DEFAULT_SYMBOLS)

    def test_only_lbank_futures_is_enabled(self):
        self.assertEqual(EXCHANGES, ("lbank",))
        with self.assertRaises(ValueError):
            fetch_snapshot(["BTCUSDT"], exchanges=["binance"])

    @patch("mi_core.multi_exchange._fetch_lbank_snapshot")
    def test_fetch_delegates_to_central_lbank_source(self, fetcher):
        fetcher.return_value = {"exchange": "lbank", "market": "futures", "rows": []}
        result = fetch_snapshot(["BTCUSDT"])
        self.assertEqual(result["exchange"], "lbank")
        self.assertEqual(result["market"], "futures")
        fetcher.assert_called_once_with(symbols=["BTCUSDT"])


if __name__ == "__main__":
    unittest.main()
