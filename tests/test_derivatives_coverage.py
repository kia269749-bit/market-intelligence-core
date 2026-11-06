import unittest

from mi_core.models import MarketBar
from mi_core.multi_asset_forecast import derivative_coverage, rank_assets


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

    def test_derivatives_do_not_change_rank_until_validated(self):
        missing = rank_assets({"BTC": self._bars(False)})[0]
        present = rank_assets({"BTC": self._bars(True)})[0]
        self.assertEqual(missing["score"], present["score"])
        self.assertEqual(present["oi_coverage_pct"], 100.0)
        self.assertEqual(present["funding_coverage_pct"], 100.0)
        self.assertFalse(present["derivatives_features_enabled"])


if __name__ == "__main__":
    unittest.main()
