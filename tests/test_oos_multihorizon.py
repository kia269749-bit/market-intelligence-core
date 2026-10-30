import unittest
from unittest.mock import patch
from mi_core.models import MarketBar
from mi_core.oos_multihorizon import evaluate_project60_multihorizon

class MultiHorizonOOSTests(unittest.TestCase):
    def test_central_cost_policy_changes_oos_economic_threshold(self):
        from mi_core import oos_multihorizon as module

        fake_result = {
            "available": True,
            "resolved": 1,
            "model_version": "wf-logit-v3-no-leak",
            "predictions": [{"actual_return_pct": 1.0, "pred": 1}],
        }
        fake_metrics = {"resolved": 1, "accuracy": 1.0,
                        "high_conf_samples": 1, "high_conf_accuracy": 1.0}
        with patch.object(module, "walk_forward_forecast", return_value=fake_result), \
             patch.object(module, "score_predictions", return_value=fake_metrics):
            base = evaluate_project60_multihorizon([], horizons=(5,), cost_policy="base")
            strict = evaluate_project60_multihorizon([], horizons=(5,), cost_policy="strict")

        base_row = base["horizons"]["5"]
        strict_row = strict["horizons"]["5"]
        # $4 / $500 = 0.80%; add 0.15% base or 0.45% strict cost.
        self.assertAlmostEqual(base_row["required_move_pct"], 0.95)
        self.assertAlmostEqual(strict_row["required_move_pct"], 1.25)
        self.assertEqual(base["round_trip_cost_pct"], 0.15)
        self.assertEqual(strict["round_trip_cost_pct"], 0.45)
        self.assertEqual(base_row["usd4_hit_rate"], 1.0)
        self.assertEqual(strict_row["usd4_hit_rate"], 0.0)

    def test_unknown_cost_policy_fails_closed(self):
        with self.assertRaises(ValueError):
            evaluate_project60_multihorizon([], horizons=(5,), cost_policy="unknown")

    def test_is_research_only_and_leakage_safe(self):
        price=100.0; bars=[]
        for i in range(520):
            price*=1.0002
            bars.append(MarketBar(i,"BTC",price,oi=1000+i,funding=0.00001,buy_volume=60,sell_volume=40))
        r=evaluate_project60_multihorizon(bars,horizons=(5,15,60))
        self.assertTrue(r["research_only"]); self.assertFalse(r["live_orders"])
        self.assertEqual(set(r["horizons"]),{"5","15","60"})
        for row in r["horizons"].values():
            self.assertEqual(row["model_version"],"wf-logit-v3-no-leak")

if __name__=="__main__": unittest.main()
