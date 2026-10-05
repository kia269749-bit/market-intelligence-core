import unittest
from mi_core.fomo_normalizer import dedupe_snapshots, normalize_leaderboard

class FomoNormalizerTests(unittest.TestCase):
    def test_normalizes_documented_fields(self):
        payload={'traders':[{'rank':3,'handle':'alpha','userId':'u1','displayName':'Alpha','pnlUsd':'1250.5','volumeUsd':50000,'trades':42,'followers':9,'holdings':4,'wallets':2,'verified':True}]}
        rows=normalize_leaderboard(payload,window='7d',captured_at=123)
        self.assertEqual(len(rows),1); self.assertEqual(rows[0].trader_id,'u1'); self.assertEqual(rows[0].pnl_usd,1250.5); self.assertEqual(rows[0].trades,42); self.assertTrue(rows[0].verified)

    def test_skips_and_dedupes(self):
        rows=normalize_leaderboard({'traders':[{'pnlUsd':10},{'handle':'alpha','userId':'u1'}]},window='24h',captured_at=123)
        self.assertEqual(len(rows),1); self.assertEqual(len(dedupe_snapshots(rows+rows)),1)

    def test_does_not_invent_trades(self):
        rows=normalize_leaderboard({'traders':[{'handle':'alpha'}]},window='all',captured_at=1)
        self.assertEqual(rows[0].pnl_usd,0.0); self.assertEqual(rows[0].trades,0)

if __name__=='__main__': unittest.main()
