import inspect, unittest
from mi_core import backtest, costs
from mi_core.profitability_gate import evaluate_setup

def _d(fn):
    return {k: v.default for k, v in inspect.signature(fn).parameters.items()
            if v.default is not inspect.Parameter.empty}

class CostConsistency(unittest.TestCase):
    def test_policy_values(self):
        self.assertEqual(costs.get_round_trip_cost_pct("base"), 0.15)
        self.assertEqual(costs.get_round_trip_cost_pct("strict"), 0.45)
    def test_backtest_default_near_base(self):
        d = _d(backtest.run)
        rt = 2 * (d["fee_bps"] + d["slippage_bps"]) / 100
        self.assertAlmostEqual(rt, costs.BASE_ROUND_TRIP_COST_PCT, delta=0.02)
    def test_gate_default_near_strict(self):
        d = _d(evaluate_setup)
        rt = 2 * (d["fee_bps"] + d["spread_bps"] + d["slippage_bps"]) / 100
        self.assertAlmostEqual(rt, costs.STRICT_ROUND_TRIP_COST_PCT, delta=0.02)

if __name__ == "__main__":
    unittest.main()
