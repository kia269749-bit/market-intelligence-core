import unittest
from mi_core.fomo_direction import TradeDirection, infer_direction

class FomoDirectionTests(unittest.TestCase):
    def test_balances_confirm_buy(self):
        r = infer_direction(target_token_delta=100, quote_token_delta=-50)
        self.assertEqual(r.direction, TradeDirection.BUY); self.assertTrue(r.reliable)
    def test_balances_confirm_sell(self):
        r = infer_direction(target_token_delta=-100, quote_token_delta=50)
        self.assertEqual(r.direction, TradeDirection.SELL); self.assertTrue(r.reliable)
    def test_dex_and_delta_agree(self):
        r = infer_direction(target_token_delta=100, quote_token_delta=-50, dex_direction="BUY")
        self.assertEqual(r.direction, TradeDirection.BUY); self.assertGreaterEqual(r.confidence, .60)
    def test_conflict_is_unknown(self):
        r = infer_direction(target_token_delta=100, quote_token_delta=-50, dex_direction="SELL")
        self.assertEqual(r.direction, TradeDirection.UNKNOWN); self.assertFalse(r.reliable); self.assertTrue(r.conflicts)
    def test_no_evidence_is_unknown(self):
        r = infer_direction(target_token_delta=0)
        self.assertEqual(r.direction, TradeDirection.UNKNOWN); self.assertFalse(r.reliable)
    def test_clmm_input_evidence(self):
        r = infer_direction(target_token_delta=100, quote_token_delta=-50, clmm_is_base_input=True)
        self.assertEqual(r.direction, TradeDirection.BUY)

if __name__ == "__main__": unittest.main()
