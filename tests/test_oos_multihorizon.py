import unittest

from mi_core.models import MarketBar
from mi_core.oos_multihorizon import (
    DEFAULT_FIT_EVERY,
    _prediction_diagnostics,
    evaluate_project60_multihorizon,
)


class MultiHorizonOOSTests(unittest.TestCase):
    def test_is_research_only_and_leakage_safe(self):
        price = 100.0
        bars = []
        for i in range(520):
            price *= 1.0002
            bars.append(
                MarketBar(
                    i,
                    "BTC",
                    price,
                    oi=1000 + i,
                    funding=0.00001,
                    buy_volume=60,
                    sell_volume=40,
                )
            )
        result = evaluate_project60_multihorizon(bars, horizons=(5, 15, 60))
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertEqual(set(result["horizons"]), {"5", "15", "60"})
        for row in result["horizons"].values():
            self.assertEqual(row["model_version"], "wf-logit-v3-no-leak")
            self.assertEqual(row["fit_every"], DEFAULT_FIT_EVERY)
            self.assertEqual(row["fit_every"], 20)
            self.assertIn("predicted_class_counts", row)
            self.assertIn("confusion_actual_rows_predicted_columns", row)
            self.assertIn("mfe_usd4_touch_rate", row)

    def test_class_balance_and_path_touch_diagnostics(self):
        result = {
            "predictions": [
                {"pred": 0, "actual": 0, "favorable_mfe_pct": 0.0},
                {"pred": 1, "actual": 1, "favorable_mfe_pct": 1.2},
                {"pred": -1, "actual": 1, "favorable_mfe_pct": 2.5},
            ]
        }
        capital = {
            "min_required_move_pct": 1.15,
            "preferred_required_move_pct": 2.35,
        }
        d = _prediction_diagnostics(result, capital)
        self.assertEqual(d["predicted_class_counts"], {"DOWN": 1, "FLAT": 1, "UP": 1})
        self.assertEqual(d["actual_class_counts"], {"DOWN": 0, "FLAT": 1, "UP": 2})
        self.assertEqual(d["directional_prediction_count"], 2)
        self.assertEqual(d["mfe_usd4_touch_rate"], 1.0)
        self.assertEqual(d["mfe_usd10_touch_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
