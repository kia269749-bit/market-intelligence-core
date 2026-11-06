import json
import tempfile
import unittest
from pathlib import Path

from mi_core.models import MarketBar
from mi_core.multi_asset_forecast import derivative_coverage, load_project60_assets, rank_assets


class DerivativeCoverageTests(unittest.TestCase):
    def _bars(self, derivatives=False):
        bars = []
        for i in range(70):
            values = {"oi": 1000.0 + i, "funding": 0.0001} if derivatives else {}
            bars.append(MarketBar(
                ts=i * 60_000,
                symbol="BTC",
                price=100.0 + i * 0.1,
                buy_volume=120.0,
                sell_volume=80.0,
                **values,
            ))
        return bars

    def test_missing_derivatives_are_reported_not_neutralized(self):
        series = {"BTC": self._bars(False)}
        coverage = derivative_coverage(series)["BTC"]
        ranked = rank_assets(series)[0]
        self.assertEqual(coverage["oi_coverage_pct"], 0.0)
        self.assertEqual(coverage["funding_coverage_pct"], 0.0)
        self.assertIsNone(ranked["oi_change"])
        self.assertFalse(ranked["derivatives_features_enabled"])

    def test_project60_loader_preserves_derivative_timestamps_and_freshness(self):
        now = 10 * 60 * 60 * 1000
        row = {
            "timestamp": now,
            "coins": {
                "BTC": {
                    "price": 100.0,
                    "open_interest": 12.0,
                    "funding": 0.0001,
                    "derivatives": {
                        "oi_timestamp_ms": now - 60 * 60 * 1000,
                        "funding_timestamp_ms": now - 4 * 60 * 60 * 1000,
                        "oi_age_ms": 60 * 60 * 1000,
                        "funding_age_ms": 4 * 60 * 60 * 1000,
                    },
                }
            },
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "project60.jsonl"
            path.write_text(json.dumps(row) + "\\n", encoding="utf-8")
            series = load_project60_assets(path)
        coverage = derivative_coverage(series)["BTC"]
        self.assertEqual(coverage["oi_fresh_coverage_pct"], 100.0)
        self.assertEqual(coverage["funding_fresh_coverage_pct"], 100.0)
        self.assertEqual(coverage["oi_timestamped_present"], 1)
        self.assertFalse(coverage["derivatives_features_enabled"])

    def test_derivatives_do_not_change_rank_until_validated(self):
        missing = rank_assets({"BTC": self._bars(False)})[0]
        present = rank_assets({"BTC": self._bars(True)})[0]
        self.assertEqual(missing["score"], present["score"])
        self.assertEqual(present["oi_coverage_pct"], 100.0)
        self.assertEqual(present["funding_coverage_pct"], 100.0)
        self.assertFalse(present["derivatives_features_enabled"])


if __name__ == "__main__":
    unittest.main()
