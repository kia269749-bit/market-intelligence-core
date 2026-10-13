import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mi_core.live_brain import _validated_forecast_from_project60


class ForecastMetadataTests(unittest.TestCase):
    def test_selected_forecast_contains_price_asset_and_horizon(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market.jsonl"
            rows = []
            for i in range(105):
                rows.append({
                    "timestamp": 1700000000 + i * 84,
                    "coins": {"BTC": {"price": 100.0 + i * 0.1}}
                })
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            def fake_forecast(bars, horizon, train_window):
                return {
                    "available": True,
                    "horizon_bars": horizon,
                    "expected_return_pct": 1.0,
                    "confidence": 0.8,
                    "current_move_pct": 0.0,
                }

            with patch(
                "mi_core.validated_forecast.forecast_now",
                side_effect=fake_forecast,
            ):
                result = _validated_forecast_from_project60(str(path), "BTC")

            self.assertTrue(result["available"])
            selected = result["selected"]
            self.assertAlmostEqual(selected["current_price"], 110.4)
            self.assertEqual(selected["asset"], "BTC")
            self.assertEqual(selected["horizon_bars"], 60)
            self.assertEqual(selected["ts"], 1700000000 + 104 * 84)
            self.assertTrue(result["research_only"])
            self.assertFalse(result["live_orders"])


if __name__ == "__main__":
    unittest.main()
