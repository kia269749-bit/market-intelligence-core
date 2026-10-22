import json
import tempfile
import unittest
from pathlib import Path

from mi_core.cli import _project60_current_prices


class Project60JournalPriceSourceTests(unittest.TestCase):
    def test_rejects_latest_hyperliquid_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            path.write_text(
                json.dumps({
                    "timestamp": 1791257623,
                    "source": "lbank_contract_marketData",
                    "market": "futures",
                    "product_group": "SwapU",
                    "coins": {"BTC": {"price": 100.0}},
                }) + "\n" + json.dumps({
                    "timestamp": 1791257683,
                    "source": "hyperliquid",
                    "coins": {"BTC": {"price": 200.0}, "ETH": {"price": 10.0}},
                }) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(_project60_current_prices(str(path)), {})

    def test_accepts_explicit_lbank_futures_prices(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            path.write_text(json.dumps({
                "timestamp": 1791257623,
                "source": "lbank_contract_marketData",
                "market": "futures",
                "product_group": "SwapU",
                "coins": {
                    "btc": {"price": "100.5"},
                    "ETH": {"price": 2000.0},
                    "SOL": {"price": 0},
                    "XRP": {"price": "bad"},
                },
            }) + "\n", encoding="utf-8")
            self.assertEqual(
                _project60_current_prices(str(path)),
                {"BTC": 100.5, "ETH": 2000.0},
            )

    def test_wrong_contract_group_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            path.write_text(json.dumps({
                "timestamp": 1791257623,
                "source": "lbank_contract_marketData",
                "market": "futures",
                "product_group": "CoinM",
                "coins": {"BTC": {"price": 100.0}},
            }) + "\n", encoding="utf-8")
            self.assertEqual(_project60_current_prices(str(path)), {})


if __name__ == "__main__":
    unittest.main()
