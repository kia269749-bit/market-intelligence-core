import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mi_core.real_validation import _directional_metrics, validate_project60


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
        self.assertAlmostEqual(result["net_profit_usd"], -2.75, places=4)
        self.assertLess(result["expectancy_usd"], 0.0)
        self.assertEqual(result["positive_net_outcomes"], 2)

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


if __name__ == "__main__":
    unittest.main()
