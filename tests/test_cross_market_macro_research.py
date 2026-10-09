import math
import unittest
from datetime import date, datetime, timedelta, timezone

from mi_core.models import MarketBar
from tools.cross_market_macro_research import (
    build_aligned_dataset,
    parse_fred_csv,
    run_research,
)


def make_bars(n=500):
    start = date(2024, 1, 1)
    bars = []
    for i in range(n):
        close = 100.0 + 0.02 * i + 1.5 * math.sin(i / 8.0)
        op = close * (1.0 + 0.001 * math.sin(i / 3.0))
        bars.append(MarketBar(
            ts=int(datetime.combine(start + timedelta(days=i), datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000),
            symbol="BTCUSDT", price=close, open=op,
            high=max(close, op) * 1.01, low=min(close, op) * 0.99,
        ))
    return bars


def make_macro(n=600):
    start = date(2023, 9, 1)
    result = {}
    for j, name in enumerate(("usd_broad", "sp500", "gold", "wti_oil", "vix")):
        series = []
        value = 100.0 + j
        for i in range(n):
            value *= 1.0 + 0.0008 * math.sin(i / (4.0 + j)) + 0.0002 * math.cos(i / 9.0 + j)
            series.append((start + timedelta(days=i), value))
        result[name] = series
    return result


class CrossMarketMacroResearchTests(unittest.TestCase):
    def test_fred_csv_parser_skips_missing_observations(self):
        payload = "observation_date,DTWEXBGS\n2024-01-01,100.0\n2024-01-02,.\n2024-01-03,101.0\n"
        rows = parse_fred_csv(payload, "DTWEXBGS")
        self.assertEqual(rows, [(date(2024, 1, 1), 100.0), (date(2024, 1, 3), 101.0)])

    def test_macro_features_are_lagged_before_crypto_target_date(self):
        bars = make_bars(12)
        macro = {"usd_broad": [
            (date(2024, 1, 1) + timedelta(days=i), 100.0 + i) for i in range(20)
        ]}
        dataset = build_aligned_dataset(bars, macro)
        row = next(item for item in dataset if item["date"] == "2024-01-10")
        # Target date 2024-01-10 uses the latest available macro observation
        # no later than 2024-01-08, i.e. the 7->8 change, not same-day data.
        expected = ((107.0 / 106.0) - 1.0) * 100.0
        self.assertAlmostEqual(row["features"]["usd_broad"], expected, places=6)

    def test_macro_model_is_research_only_and_reports_untouched_holdout(self):
        result = run_research(make_bars(), make_macro(), cost_round_trip_pct=0.35, capital_usd=500)
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["training_samples"], 100)
        self.assertGreater(result["holdout_samples"], 0)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertFalse(result["trade_ready"])
        self.assertIn("macro_ols_cost_aware", result)
        self.assertIn("buy_and_hold_baseline", result)


if __name__ == "__main__":
    unittest.main()
