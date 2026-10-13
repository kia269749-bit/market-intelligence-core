import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mi_core.real_validation import (
    _directional_metrics,
    _oos_integrity_metrics,
    _path_excursion_metrics,
    _opportunity_tier,
    validate_project60,
)


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

    def test_time_window_metrics_report_elapsed_time_and_gaps(self):
        from mi_core.real_validation import _time_window_metrics
        metrics = _time_window_metrics({"predictions": [
            {"elapsed_seconds": 3600, "window_gap_count_over_300s": 0, "window_max_gap_seconds": 83},
            {"elapsed_seconds": 5400, "window_gap_count_over_300s": 1, "window_max_gap_seconds": 420},
            {"elapsed_seconds": 7200, "window_gap_count_over_300s": 1, "window_max_gap_seconds": 600},
        ]})
        self.assertTrue(metrics["available"])
        self.assertEqual(metrics["samples"], 3)
        self.assertEqual(metrics["windows_with_gap_over_300s"], 2)
        self.assertEqual(metrics["max_gap_seconds"], 600)

    def test_non_overlapping_predictions_use_bar_indices(self):
        from mi_core.validated_forecast import non_overlapping_predictions
        rows = [
            {"bar_index": i, "ts": 1790000000 + i * 83, "pred": 1, "actual": 1}
            for i in range(10)
        ]
        sampled = non_overlapping_predictions(
            {"horizon_bars": 3, "predictions": rows}, require_actual=True
        )
        self.assertEqual([x["bar_index"] for x in sampled], [0, 3, 6, 9])

    def test_gap_clean_predictions_excludes_long_and_unmeasured_gaps(self):
        from mi_core.real_validation import _gap_clean_predictions
        rows = [
            {"bar_index": 0, "window_gap_count_over_300s": 0, "window_max_gap_seconds": 83},
            {"bar_index": 60, "window_gap_count_over_300s": 1, "window_max_gap_seconds": 420},
            {"bar_index": 120, "window_gap_count_over_300s": 0, "window_max_gap_seconds": 301},
            {"bar_index": 180},
        ]
        clean = _gap_clean_predictions(rows)
        self.assertEqual([x["bar_index"] for x in clean], [0])

    def test_side_diagnostics_compare_long_short_and_baselines_after_costs(self):
        from mi_core.real_validation import _side_and_baseline_diagnostics
        result = _side_and_baseline_diagnostics({"predictions": [
            {"pred": 1, "actual_return_pct": 1.0},
            {"pred": -1, "actual_return_pct": -0.8},
            {"pred": 0, "actual_return_pct": 0.2},
        ]}, capital_usd=500.0, round_trip_cost_pct=0.35)
        self.assertEqual(result["model_long"]["trades"], 1)
        self.assertEqual(result["model_short"]["trades"], 1)
        self.assertAlmostEqual(result["model_long"]["net_profit_usd"], 3.25, places=4)
        self.assertAlmostEqual(result["model_short"]["net_profit_usd"], 2.25, places=4)
        self.assertEqual(result["always_long_same_windows"]["trades"], 3)
        self.assertEqual(result["model_abstained_windows"], 1)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

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


    def test_oos_integrity_detects_class_collapse_and_majority_baseline(self):
        result = {
            "accuracy": 1.0,
            "predictions": [
                {"ts": 1790000000 + i * 83, "bar_index": i, "pred": -1, "actual": -1}
                for i in range(10)
            ],
        }
        metrics = _oos_integrity_metrics(result, 120)
        self.assertTrue(metrics["class_collapse"])
        self.assertEqual(metrics["actual_class_count"], 1)
        self.assertEqual(metrics["prediction_class_count"], 1)
        self.assertEqual(metrics["majority_baseline_accuracy"], 1.0)
        self.assertEqual(metrics["model_vs_majority_accuracy_lift"], 0.0)
        self.assertEqual(metrics["overlap_rate"], 1.0)

    def test_oos_integrity_shows_real_accuracy_lift_without_collapse(self):
        result = {
            "accuracy": 0.75,
            "predictions": [
                {"ts": 1790000000, "bar_index": 0, "pred": -1, "actual": -1},
                {"ts": 1790007200, "bar_index": 120, "pred": 1, "actual": 1},
                {"ts": 1790014400, "bar_index": 240, "pred": -1, "actual": 1},
                {"ts": 1790021600, "bar_index": 360, "pred": 1, "actual": -1},
            ],
        }
        metrics = _oos_integrity_metrics(result, 120)
        self.assertFalse(metrics["class_collapse"])
        self.assertEqual(metrics["majority_baseline_accuracy"], 0.5)
        self.assertEqual(metrics["model_vs_majority_accuracy_lift"], 0.25)
        self.assertEqual(metrics["overlap_rate"], 0.0)

    def test_class_collapse_blocks_watch(self):
        tier = _opportunity_tier(
            {"high_conf_accuracy": 1.0},
            {"net_profit_usd": 100.0, "expectancy_usd": 1.0},
            {"min_target_hit_rate": 0.50},
            {"class_collapse": True},
        )
        self.assertEqual(tier, "NO_TRADE")

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
