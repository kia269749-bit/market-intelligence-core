import unittest
from unittest.mock import patch

from mi_core.lbank_futures import fetch_orderbook, fetch_snapshot, normalize_symbol


class LBankFuturesTests(unittest.TestCase):
    def test_symbol_normalization(self):
        self.assertEqual(normalize_symbol("BTC/USDT"), "BTCUSDT")
        self.assertEqual(normalize_symbol("btc_usdt"), "BTCUSDT")

    @patch("mi_core.lbank_futures._get_json")
    def test_orderbook_parses_levels_and_computes_metrics(self, get_json):
        get_json.return_value = {
            "success": True,
            "data": {
                "symbol": "BTCUSDT",
                "bids": [
                    {"price": "99", "volume": "2", "orders": 2},
                    {"price": "100", "volume": "3", "orders": 4},
                ],
                "asks": [
                    {"price": "102", "volume": "1", "orders": 1},
                    {"price": "101", "volume": "1", "orders": 2},
                ],
            },
        }
        result = fetch_orderbook("btc_usdt", depth=2)
        self.assertEqual(result["exchange"], "lbank")
        self.assertEqual(result["market"], "futures")
        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertEqual(result["best_bid"], 100.0)
        self.assertEqual(result["best_ask"], 101.0)
        self.assertAlmostEqual(result["spread_pct"], (1 / 100.5) * 100)
        self.assertAlmostEqual(result["volume_imbalance_pct"], (3 / 7) * 100)
        self.assertEqual(result["data_quality"], "HEALTHY")
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        get_json.assert_called_once()

    @patch("mi_core.lbank_futures._get_json")
    def test_orderbook_rejects_missing_valid_levels(self, get_json):
        get_json.return_value = {"bids": [], "asks": []}
        with self.assertRaises(RuntimeError):
            fetch_orderbook("BTCUSDT")

    def test_orderbook_rejects_invalid_depth(self):
        with self.assertRaises(ValueError):
            fetch_orderbook("BTCUSDT", depth=0)

    @patch("mi_core.lbank_futures.fetch_market_rows")
    def test_snapshot_uses_only_lbank_and_marks_missing_contract_unsafe(self, fetch_rows):
        fetch_rows.return_value = [{
            "exchange": "lbank", "market": "futures", "symbol": "BTCUSDT",
            "price": 65000.0, "mark_price": 65001.0, "funding_rate": 0.0001,
            "volume_24h": 1.0, "turnover_24h": 65000.0, "source": "test",
        }]
        result = fetch_snapshot(["BTCUSDT", "ETHUSDT"])
        self.assertEqual(result["exchange"], "lbank")
        self.assertEqual(result["market"], "futures")
        self.assertEqual(result["data_quality"]["status"], "DEGRADED")
        self.assertEqual([row["symbol"] for row in result["rows"]], ["BTCUSDT"])
        self.assertEqual(result["errors"][0]["error"], "contract_not_found")
        self.assertIsNone(result["aggregates"][0]["cross_exchange_spread_pct"])
        self.assertFalse(result["live_orders"])


if __name__ == "__main__":
    unittest.main()
