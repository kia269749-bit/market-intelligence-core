import unittest
from mi_core.profitability_gate import evaluate_buy
from mi_core.paper_journal import resolve_signal

class ProfitabilityGateTests(unittest.TestCase):
    def test_cost_can_reject_weak_edge(self):
        r=evaluate_buy(100,99.2,101.2,0.80)
        self.assertFalse(r.approved)
        self.assertIn(r.reason, ("risk_reward_below_gate","edge_too_small_after_costs"))

    def test_strong_net_edge_passes(self):
        r=evaluate_buy(100,99.2,103.0,0.80)
        self.assertTrue(r.approved)
        self.assertGreaterEqual(r.net_rr,1.50)

    def test_shadow_resolution(self):
        self.assertEqual(resolve_signal(100,103,"BULLISH",99,102),"TARGET")
        self.assertEqual(resolve_signal(100,98,"BULLISH",99,102),"STOP")
        self.assertEqual(resolve_signal(100,101,"BULLISH",99,102),"OPEN")

if __name__=="__main__": unittest.main()
