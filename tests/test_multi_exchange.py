import unittest
from unittest.mock import patch

from mi_core.multi_exchange import DEFAULT_SYMBOLS, EXCHANGES, fetch_snapshot


class MultiExchangeCompatibilityTests(unittest.TestCase):
    def test_default_universe(self):
        self.assertGreaterEqual(len(DEFAULT_SYMBOLS), 10)
        self.assertIn("BTCUSDT", DEFAULT_SYMBOLS)
        self.assertIn("ETHUSDT", DEFAULT_SYMBOLS)

    def test_only_configured_market_data_source_is_enabled(self):
        self.assertEqual(EXCHANGES, ("hyperliquid",))
        with self.assertRaises(ValueError):
            fetch_snapshot(["BTCUSDT"], exchanges=["binance"])
        with self.assertRaises(ValueError):
            fetch_snapshot(["BTCUSDT"], exchanges=["lbank"])

    @patch("mi_core.multi_exchange._fetch_hyperliquid_snapshot")
    def test_fetch_delegates_to_hyperliquid_feed(self, fetcher):
        fetcher.return_value = {
            "exchange": "hyperliquid",
            "market": "perpetuals",
            "rows": [],
            "cost_model_exchange": "lbank",
        }
        result = fetch_snapshot(["BTCUSDT"])
        self.assertEqual(result["exchange"], "hyperliquid")
        self.assertEqual(result["market"], "perpetuals")
        self.assertEqual(result["cost_model_exchange"], "lbank")
        fetcher.assert_called_once_with(symbols=["BTCUSDT"])


if __name__ == "__main__":
    unittest.main()
