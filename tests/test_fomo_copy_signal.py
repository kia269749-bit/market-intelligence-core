import unittest
from mi_core.fomo_copy_signal import build_fomo_copy_signal, rank_fomo_copy_signals
from mi_core.fomo_smart_money import TraderAction, TrackedPosition
from mi_core.fomo_trader_confidence import FomoTraderConfidence
from mi_core.meme_candidate_scoring import score_meme_candidate

class FomoCopySignalTests(unittest.TestCase):
    def setUp(self):
        self.trader = FomoTraderConfidence("t1", .90, .90, .90, 1.0, .90, .91, True)
        self.candidate = score_meme_candidate("MEME", liquidity_usd=2_000_000, volume_24h_usd=10_000_000, holders=15_000, top_holder_pct=8, buy_sell_ratio=1.8, smart_money_score=.95, fomo_score=.85)

    def test_buy_becomes_follow_candidate(self):
        s=build_fomo_copy_signal(TraderAction("t1","MEME","BUY",100,1.0,5000),self.trader,self.candidate)
        self.assertEqual(s.status,"FOLLOW_CANDIDATE"); self.assertGreater(s.score,.70)
    def test_unqualified_trader_is_blocked(self):
        weak=FomoTraderConfidence("t1",.9,.9,.9,.2,.9,.55,False)
        s=build_fomo_copy_signal(TraderAction("t1","MEME","BUY",100,1.0,5000),weak,self.candidate)
        self.assertEqual(s.status,"IGNORE_UNQUALIFIED_TRADER")
    def test_high_risk_is_blocked(self):
        risky=score_meme_candidate("RISK",liquidity_usd=10_000,volume_24h_usd=100_000,holders=20,top_holder_pct=60,buy_sell_ratio=.5,smart_money_score=.9,fomo_score=.9)
        s=build_fomo_copy_signal(TraderAction("t1","RISK","BUY",100,1.0,5000),self.trader,risky)
        self.assertEqual(s.status,"BLOCK_HIGH_RISK")
    def test_sell_becomes_exit_watch(self):
        p=TrackedPosition("t1","MEME",1.0,5000,100,1.2,20.0,100)
        s=build_fomo_copy_signal(TraderAction("t1","MEME","SELL",200,1.2,5000),self.trader,self.candidate,position=p)
        self.assertEqual(s.status,"EXIT_WATCH"); self.assertEqual(s.position_return_pct,20.0)
    def test_ranking(self):
        a=build_fomo_copy_signal(TraderAction("t1","MEME","BUY",100,1.0,5000),self.trader,self.candidate)
        b=build_fomo_copy_signal(TraderAction("t1","MEME","SELL",200,1.2,5000),self.trader,self.candidate)
        self.assertEqual(rank_fomo_copy_signals([b,a])[0].status,"FOLLOW_CANDIDATE")

if __name__ == "__main__": unittest.main()
