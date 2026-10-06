import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mi_core.real_validation import _directional_metrics, _path_excursion_metrics, _opportunity_tier, validate_project60


class RealValidationTests(unittest.TestCase):
    def test_directional_metrics_accounts_for_costs(self):
        result = _directional_metrics(
            {"predictions": [
                {"pred": 1, "actual_return_pct": 1.0},
                {"pred": -1, "actual_return_pct": 0.5},
                {"pred": 1, "actual_return_pct": -1.0},
            ]},
            capital_usd=500.0,
            round_trip_cost_pct=0.35,
        )
        self.assertEqual(result["directional_predictions"], 3)
        self.assertAlmostEqual(result["net_profit_usd"], -7.75, places=4)
        self.assertLess(result["expectancy_usd"], 0.0)
        self.assertEqual(result["positive_net_outcomes"], 1)

    def test_path_excursion_metrics_measure_targets_and_adverse_move(self):
        result = _path_excursion_metrics({"predictions": [
            {"pred": 1, "favorable_mfe_pct": 2.5, "adverse_mae_pct": 0.6},
            {"pred": -1, "favorable_mfe_pct": 1.2, "adverse_mae_pct": 1.4},
        ]})
        self.assertEqual(result["target_hit_rates"]["1.15"], 1.0)
        self.assertEqual(result["target_hit_rates"]["2.35"], 0.5)
        self.assertEqual(result["adverse_excursion_rates"]["1.0"], 0.5)

    def test_positive_but_not_gate_pass_is_watch(self):
        tier = _opportunity_tier(
            {"high_conf_accuracy": 0.80},
            {"net_profit_usd": 20.0, "expectancy_usd": 0.40},
            {"min_target_hit_rate": 0.20},
        )
        self.assertEqual(tier, "WATCH")

    def test_validation_is_research_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            path.write_text("", encoding="utf-8")
            with patch("mi_core.real_validation.load_project60_assets", return_value={}):
                with patch("mi_core.real_validation.rank_assets", return_value=[]):
                    result = validate_project60(str(path))
        self.assertFalse(result["available"])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

    def test_output_schema_keeps_policy(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            path.write_text("", encoding="utf-8")
            with patch("mi_core.real_validation.load_project60_assets", return_value={}):
                with patch("mi_core.real_validation.rank_assets", return_value=[]):
                    result = validate_project60(str(path))
        self.assertEqual(result["policy"]["capital_usd"], 500.0)
        self.assertEqual(result["policy"]["min_profit_usd"], 4.0)
        self.assertEqual(result["policy"]["preferred_profit_usd"], 10.0)


    def test_short_horizon_is_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            path.write_text("", encoding="utf-8")
            with patch("mi_core.real_validation.load_project60_assets", return_value={}):
                with patch("mi_core.real_validation.rank_assets", return_value=[]):
                    result = validate_project60(str(path), horizon=30, horizons=[30, 60])
        short = next(x for x in result["horizon_results"] if x["horizon_bars"] == 30)
        long = next(x for x in result["horizon_results"] if x["horizon_bars"] == 60)
        self.assertFalse(short["signal_eligible"])
        self.assertTrue(long["signal_eligible"])
        self.assertEqual(short["accepted_assets"], 0)

if __name__ == "__main__":
    unittest.main()
