import json
import math
import tempfile
import unittest
from pathlib import Path

from mi_core.multi_asset_forecast import load_project60_assets, rank_assets
from mi_core.live_brain import _validated_forecast_from_project60


def row(ts, price=60000.0):
    return {
        "timestamp": ts,
        "coins": {
            "BTC": {
                "price": price,
                "open_interest": 1000.0,
                "funding": 0.0001,
                "trades": {"buy_usd": 100.0, "sell_usd": 80.0},
                "orderbook": {"bid_usd": 500.0, "ask_usd": 450.0},
            }
        },
    }


class Project60DirectLoaderValidationTests(unittest.TestCase):
    def write_rows(self, rows):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "market.jsonl"
        path.write_text(
            "".join(json.dumps(item, allow_nan=True) + "\n" for item in rows),
            encoding="utf-8",
        )
        return path

    def test_multi_asset_loader_skips_nonfinite_price_and_bad_chronology(self):
        path = self.write_rows([
            row(100, 60000),
            row(200, float("nan")),
            row(150, 60100),
            row(300, 60300),
            row(300, 60400),
            row(400, 60500),
        ])
        bars = load_project60_assets(path, max_rows=100)["BTC"]
        timestamps = [bar.ts for bar in bars]
        prices = [bar.price for bar in bars]
        self.assertEqual(timestamps, [100, 300, 400])
        self.assertTrue(all(math.isfinite(p) and p > 0 for p in prices))
        self.assertTrue(all(a < b for a, b in zip(timestamps, timestamps[1:])))

    def test_live_loader_does_not_forecast_from_short_dirty_history(self):
        path = self.write_rows([
            row(100, 60000),
            row(200, float("inf")),
            row(150, 60100),
            row(300, 60300),
        ])
        result = _validated_forecast_from_project60(path, asset="BTC")
        self.assertIs(result.get("available"), False)
        self.assertEqual(result.get("reason"), "insufficient_history")

    def test_ranker_rejects_nonfinite_or_nonchronological_series(self):
        clean_path = self.write_rows([row(100 + i * 60, 60000 + i * 10) for i in range(70)])
        clean = load_project60_assets(clean_path, max_rows=100)
        self.assertTrue(rank_assets(clean, min_samples=60))

        bars = list(clean["BTC"])
        bars[10] = type(bars[10])(
            ts=bars[9].ts,
            symbol=bars[10].symbol,
            price=bars[10].price,
            oi=bars[10].oi,
            funding=bars[10].funding,
            bid=bars[10].bid,
            ask=bars[10].ask,
            buy_volume=bars[10].buy_volume,
            sell_volume=bars[10].sell_volume,
        )
        self.assertEqual(rank_assets({"BTC": bars}, min_samples=60), [])

    def test_ranker_rejects_nonfinite_prices(self):
        clean_path = self.write_rows([row(100 + i * 60, 60000 + i * 10) for i in range(70)])
        bars = list(load_project60_assets(clean_path, max_rows=100)["BTC"])
        bad = bars[-1]
        bars[-1] = type(bad)(
            ts=bad.ts,
            symbol=bad.symbol,
            price=float("nan"),
            oi=bad.oi,
            funding=bad.funding,
            bid=bad.bid,
            ask=bad.ask,
            buy_volume=bad.buy_volume,
            sell_volume=bad.sell_volume,
        )
        self.assertEqual(rank_assets({"BTC": bars}, min_samples=60), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
