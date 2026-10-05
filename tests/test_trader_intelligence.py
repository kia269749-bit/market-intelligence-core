import unittest
from mi_core.trader_intelligence import TraderTrade, consistency_score, elite_score, max_drawdown, rank_traders, trader_metrics

class TraderIntelligenceTests(unittest.TestCase):
    def sample(self, trader='elite', n=20, pnl=100.0, meme=True):
        return [TraderTrade(trader_id=trader, symbol='MEME' if meme else 'BTC', entry_ts=i*60, exit_ts=i*60+30, entry_price=1.0, exit_price=1.1, qty=1.0, pnl_usd=pnl, invested_usd=1000.0, is_meme=meme, early_entry=(i%2==0), clean_exit=(i%3!=0), holding_minutes=30.0) for i in range(n)]
    def test_metrics(self):
        m=trader_metrics(self.sample()); self.assertEqual(m['trades'],20); self.assertAlmostEqual(m['win_rate'],1.0); self.assertGreater(m['meme_roi'],0); self.assertGreater(m['early_entry_rate'],0)
    def test_drawdown(self):
        self.assertAlmostEqual(max_drawdown([10,10,-5,-5]),0.0); self.assertGreater(max_drawdown([10,-20]),0.9)
    def test_consistency(self):
        self.assertGreater(consistency_score([0.1,0.1,0.1]),0.9); self.assertLess(consistency_score([0.5,-0.5,0.4]),0.8)
    def test_small_sample_is_not_elite(self):
        self.assertEqual(elite_score(trader_metrics(self.sample(n=5)),min_trades=20),0.0)
    def test_ranking(self):
        rows=rank_traders(self.sample('A')+self.sample('B',pnl=10.0),min_trades=20); self.assertEqual(rows[0]['trader_id'],'A'); self.assertEqual(rows[0]['rank'],1)
    def test_trade_serialization(self):
        self.assertEqual(self.sample()[0].to_dict()['trader_id'],'elite')

if __name__=='__main__': unittest.main()