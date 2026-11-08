import json
import tempfile
import unittest
from pathlib import Path

from tools.segmented_nonoverlap_oos import load


class SegmentedPriceValidationTests(unittest.TestCase):
    def test_rejects_nonfinite_nonpositive_and_invalid_prices(self):
        rows = [
            {"timestamp": 1, "coins": {"BTC": {"price": 100}}},
            {"timestamp": 2, "coins": {"BTC": {"price": float("nan")}}},
            {"timestamp": 3, "coins": {"BTC": {"price": float("inf")}}},
            {"timestamp": 4, "coins": {"BTC": {"price": float("-inf")}}},
            {"timestamp": 5, "coins": {"BTC": {"price": 0}}},
            {"timestamp": 6, "coins": {"BTC": {"price": -1}}},
            {"timestamp": 7, "coins": {"BTC": {"price": "not-a-price"}}},
            {"timestamp": 8, "coins": {"BTC": {"price": 125.5}}},
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.jsonl"
            path.write_text(
                "".join(json.dumps(row, allow_nan=True) + "\n" for row in rows),
                encoding="utf-8",
            )
            series = load(str(path))

        self.assertEqual(
            [bar.price for bar in series["BTC"]],
            [100.0, 125.5],
        )

    def test_preserves_valid_price(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.jsonl"
            path.write_text(
                '{"timestamp":1,"coins":{"BTC":{"price":123.45}}}\n',
                encoding="utf-8",
            )
            series = load(str(path))

        self.assertEqual(len(series["BTC"]), 1)
        self.assertEqual(series["BTC"][0].price, 123.45)


if __name__ == "__main__":
    unittest.main()
