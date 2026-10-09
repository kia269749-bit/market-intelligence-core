import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mi_core import cli


class ForecastTradeReadinessTests(unittest.TestCase):
    def test_forecast_gate_is_not_reported_as_trade_ready(self):
        rows = []
        for i in range(9):
            pred = 1 if i % 2 == 0 else -1
            actual = 0.8 if pred == 1 else -0.4
            rows.append({
                "ts": i * 60_000,
                "pred": pred,
                "actual": pred,
                "actual_return_pct": actual,
                "p_up": 0.8 if pred == 1 else 0.1,
                "p_flat": 0.1,
                "p_down": 0.1 if pred == 1 else 0.8,
                "favorable_mfe_pct": 1.0,
                "adverse_mae_pct": 0.2,
            })
        fake_result = {
            "available": True,
            "resolved": len(rows),
            "accuracy": 1.0,
            "predictions": rows,
            "research_only": True,
            "live_orders": False,
        }
        with tempfile.TemporaryDirectory() as td:
            out = str(Path(td) / "forecast.json")
            argv = ["mi_core.cli", "forecast-validate", "--input", "unused.jsonl",
                    "--horizon", "3", "--train-window", "60", "--out", out]
            with patch.object(sys, "argv", argv), \
                 patch("mi_core.cli.load_input", return_value=[]), \
                 patch("mi_core.cli.walk_forward_forecast", return_value=fake_result), \
                 patch("mi_core.cli.write_report") as writer:
                cli.main()
                report = writer.call_args.args[0]

        self.assertIsInstance(report["forecast_gate_passed"], bool)
        self.assertFalse(report["trade_ready"])
        self.assertIn("actual_clock_execution_validation", report["trade_readiness_reason"])
        self.assertEqual(report["overlapping_forecast_diagnostic"]["samples"], 9)
        self.assertEqual(report["economic_edge"]["samples"], 3)
        self.assertEqual(report["economic_metrics"]["directional_predictions"], 3)


if __name__ == "__main__":
    unittest.main()
