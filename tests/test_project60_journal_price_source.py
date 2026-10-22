import json
import tempfile
import unittest
from pathlib import Path

from mi_core.cli import _project60_current_prices


class Project60JournalPriceSourceTests(unittest.TestCase):
    def test_accepts_latest_hyperliquid_perpetual_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            path.write_text(json.dumps({
                "timestamp": 1791257623,
                "source": "hyperliquid",
                "coins": {"btc": {"price": "100.5"}, "ETH": {"price": 2000.0}},
            }) + "\n", encoding="utf-8")
            self.assertEqual(
                _project60_current_prices(str(path)),
                {"BTC": 100.5, "ETH": 2000.0},
            )

    def test_rejects_latest_unknown_source_instead_of_using_old_prices(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            path.write_text(
                json.dumps({
                    "timestamp": 1791257623,
                    "source": "hyperliquid",
                    "coins": {"BTC": {"price": 100.0}},
                }) + "\n" + json.dumps({
                    "timestamp": 1791257683,
                    "source": "unknown_exchange",
                    "coins": {"BTC": {"price": 200.0}},
                }) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(_project60_current_prices(str(path)), {})

    def test_rejects_invalid_prices(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            path.write_text(json.dumps({
                "timestamp": 1791257623,
                "source": "hyperliquid",
                "coins": {"BTC": {"price": "bad"}, "ETH": {"price": 0}},
            }) + "\n", encoding="utf-8")
            self.assertEqual(_project60_current_prices(str(path)), {})


if __name__ == "__main__":
    unittest.main()
