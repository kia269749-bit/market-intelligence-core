import math
import unittest
from mi_core.models import MarketBar
from tools.ensemble_strategy_tournament import build_combined_signals, evaluate_cost_matrix

def make_bars(n=800):
    bars=[]
    for i in range(n):
        close=100.0+0.035*i+2.5*math.sin(i/9.0)+0.8*math.sin(i/2.7)
        op=close*(1.0+0.0015*math.sin(i/3.0))
        bars.append(MarketBar(ts=i*86_400_000,symbol="BTCUSDT",price=close,open=op,
            high=max(op,close)*1.004,low=min(op,close)*0.996,volume=1000.0))
    return bars

class EnsembleTournamentTests(unittest.TestCase):
    def test_blends_and_component_strategies_are_available(self):
        signals=build_combined_signals(make_bars())
        self.assertIn("blend_weighted_consensus",signals)
        self.assertIn("blend_regime_adaptive",signals)
        for values in signals.values():
            self.assertEqual(len(values),800)
            self.assertTrue(set(values).issubset({-1.0,0.0,1.0}))
    def test_cost_matrix_compares_same_holdout_and_baselines(self):
        result=evaluate_cost_matrix(make_bars(),costs=(0.20,0.25,0.35))
        self.assertEqual(result["status"],"ok")
        self.assertEqual(set(result["results_by_cost"]),{"0.20%","0.25%","0.35%"})
        for strategies in result["results_by_cost"].values():
            self.assertIn("ema20_50_trend",strategies)
            self.assertIn("blend_weighted_consensus",strategies)
            self.assertGreater(strategies["blend_weighted_consensus"]["holdout_oos"]["bars"],0)
        self.assertFalse(result["trade_ready"])
        self.assertFalse(result["live_orders"])
        self.assertTrue(result["research_only"])
    def test_higher_cost_does_not_improve_same_blend_holdout(self):
        result=evaluate_cost_matrix(make_bars(),costs=(0.20,0.25,0.35))
        for strategy in ("blend_weighted_consensus","blend_regime_adaptive"):
            values=[result["results_by_cost"][key][strategy]["holdout_oos"]["ending_equity_usd"]
                    for key in ("0.20%","0.25%","0.35%")]
            self.assertGreaterEqual(values[0],values[1])
            self.assertGreaterEqual(values[1],values[2])
    def test_insufficient_data_is_not_accepted(self):
        result=evaluate_cost_matrix(make_bars(500))
        self.assertEqual(result["status"],"insufficient_data")
        self.assertFalse(result["trade_ready"])

if __name__=="__main__": unittest.main()
