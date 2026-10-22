import unittest
from unittest.mock import patch

from mi_core.lbank_futures import fetch_snapshot, normalize_symbol


class LBankFuturesTests(unittest.TestCase):
    def test_symbol_normalization(self):
        self.assertEqual(normalize_symbol("BTC/USDT"), "BTCUSDT")
        self.assertEqual(normalize_symbol("btc_usdt"), "BTCUSDT")

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
        self.assertFalse(result["live_orders"])


if __name__ == "__main__":
    unittest.main()
