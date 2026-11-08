import json
import math
import tempfile
import unittest
from pathlib import Path

from mi_core.cli import load_project60_bars


def record(ts, price=100.0):
    return {
        "timestamp": ts,
        "coins": {
            "BTC": {
                "price": price,
                "open_interest": 1000,
                "funding": 0.0001,
                "orderbook": {"bid_usd": 500, "ask_usd": 450},
                "trades": {"buy_usd": 300, "sell_usd": 200},
            }
        },
    }


class Project60LoaderValidationTests(unittest.TestCase):
    def load_records(self, records):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "market.jsonl"
            path.write_text(
                "\n".join(json.dumps(item) for item in records) + "\n",
                encoding="utf-8",
            )
            return load_project60_bars(path, "BTC", 800)

    def test_accepts_valid_chronological_rows(self):
        bars = self.load_records([record(100), record(160, 101)])
        self.assertEqual([bar.ts for bar in bars], [100, 160])
        self.assertEqual([bar.price for bar in bars], [100.0, 101.0])

    def test_skips_nonfinite_or_nonpositive_prices(self):
        bars = self.load_records([
            record(100, float("nan")),
            record(160, float("inf")),
            record(220, 0),
            record(280, 102),
        ])
        self.assertEqual([(bar.ts, bar.price) for bar in bars], [(280, 102.0)])

    def test_skips_nonfinite_or_nonpositive_timestamps(self):
        bars = self.load_records([
            record(float("nan")),
            record(float("inf")),
            record(0),
            record(100, 101),
        ])
        self.assertEqual([bar.ts for bar in bars], [100])

    def test_rejects_duplicate_timestamps(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            self.load_records([record(100), record(100, 101)])

    def test_rejects_out_of_order_timestamps(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            self.load_records([record(160), record(100, 101)])

    def test_nonfinite_optional_features_do_not_enter_bars(self):
        data = record(100)
        data["coins"]["BTC"]["funding"] = float("nan")
        data["coins"]["BTC"]["orderbook"]["bid_usd"] = float("inf")
        bars = self.load_records([data])
        self.assertEqual(len(bars), 1)
        self.assertIsNone(bars[0].funding)
        self.assertTrue(math.isfinite(bars[0].bid))
        self.assertEqual(bars[0].bid, 0.0)


if __name__ == "__main__":
    unittest.main()
