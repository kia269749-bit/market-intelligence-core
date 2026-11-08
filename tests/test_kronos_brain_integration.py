import unittest
from unittest.mock import patch

from mi_core.live_brain import run_once


class KronosBrainIntegrationTests(unittest.TestCase):
    def test_kronos_is_recorded_as_evidence_but_never_votes_or_changes_fusion(self):
        market = {
            "rows": [{"symbol": "BTCUSDT", "change_24h_pct": 0.0, "price": 100.0}],
            "data_quality": {"status": "HEALTHY", "score": 1.0},
        }
        kronos = {
            "available": True,
            "model": "Kronos",
            "scenario_count": 20,
            "scenario_up_fraction": 0.65,
            "research_only": True,
            "live_orders": False,
        }
        with patch("mi_core.live_brain.fetch_snapshot", return_value=market), \
             patch("mi_core.live_brain.scan_boosted", return_value={"candidates": []}):
            baseline = run_once()
            integrated = run_once(kronos_forecast=kronos)

        self.assertEqual(integrated["evidence"]["kronos"], kronos)
        self.assertEqual(integrated["evidence"]["combined"], baseline["evidence"]["combined"])
        self.assertNotIn("kronos", integrated["evidence"]["fusion_inputs"])
        self.assertTrue(integrated["research_only"])
        self.assertFalse(integrated["live_orders"])


if __name__ == "__main__":
    unittest.main()
