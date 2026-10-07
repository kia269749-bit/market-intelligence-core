import json
import tempfile
import unittest
from pathlib import Path

from mi_core.project60_adapter import read_snapshot, summarize


class Project60AdapterTests(unittest.TestCase):
    def test_current_schema_extracts_btc_and_eth(self):
        raw = {
            "timestamp": 1791257623,
            "datetime": "2026-10-06T03:33:43+00:00",
            "source": "hyperliquid",
            "coins": {
                "BTC": {
                    "coin": "BTC",
                    "price": 85313.0,
                    "open_interest": 38779.9986,
                    "funding": 1.25e-5,
                    "orderbook": {"imbalance_pct": 15.59},
                    "trades": {"buy_usd": 406.0, "sell_usd": 44940.9, "imbalance_pct": -98.2},
                },
                "ETH": {
                    "coin": "ETH",
                    "price": 2693.2,
                    "open_interest": 1187215.5,
                    "funding": 1.25e-5,
                    "orderbook": {"imbalance_pct": 11.82},
                    "trades": {"buy_usd": 603.8, "sell_usd": 6189.5, "imbalance_pct": -82.22},
                },
            },
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "market.jsonl"
            path.write_text(json.dumps(raw) + "\n", encoding="utf-8")
            result = read_snapshot(str(path))
            self.assertTrue(result["available"])
            self.assertEqual(result["assets"]["BTC"]["price"], 85313.0)
            self.assertEqual(result["assets"]["ETH"]["direction"], "UNKNOWN")

    def test_conflicting_asset_evidence_becomes_unknown(self):
        raw = {
            "timestamp": 1,
            "coins": {
                "BTC": {
                    "price": 1,
                    "orderbook": {"imbalance_pct": 50},
                    "trades": {"imbalance_pct": -50},
                }
            },
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "market.jsonl"
            path.write_text(json.dumps(raw) + "\n", encoding="utf-8")
            result = summarize(str(path))
            self.assertEqual(result["bias"], "UNKNOWN")
            self.assertEqual(result["confidence"], 0.0)

    def test_invalid_asset_is_tolerated(self):
        raw = {"timestamp": 1, "coins": {"ETH": {"error": "network"}}}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "market.jsonl"
            path.write_text(json.dumps(raw) + "\n", encoding="utf-8")
            result = read_snapshot(str(path))
            self.assertFalse(result["assets"]["ETH"]["available"])


if __name__ == "__main__":
    unittest.main()
