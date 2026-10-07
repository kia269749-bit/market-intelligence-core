import unittest
from mi_core.live_brain import _leader_follower_vote

class LeaderFollowerFusionTests(unittest.TestCase):
    def test_confirmed_buy_events_become_bullish_evidence(self):
        r=_leader_follower_vote({"events":[
            {"direction":"BUY","confidence":0.80},
            {"direction":"BUY","confidence":0.70},
        ]})
        self.assertTrue(r["confirmed"])
        self.assertEqual(r["direction"],"BULLISH")
        self.assertGreaterEqual(r["confidence"],0.40)

    def test_confirmed_sell_events_become_bearish_evidence(self):
        r=_leader_follower_vote({"events":[
            {"direction":"SELL","confidence":0.80},
            {"direction":"SELL","confidence":0.70},
        ]})
        self.assertTrue(r["confirmed"])
        self.assertEqual(r["direction"],"BEARISH")

    def test_conflicting_events_do_not_force_direction(self):
        r=_leader_follower_vote({"events":[
            {"direction":"BUY","confidence":0.80},
            {"direction":"SELL","confidence":0.80},
        ]})
        self.assertFalse(r["confirmed"])
        self.assertEqual(r["direction"],"UNKNOWN")

if __name__=="__main__":
    unittest.main()
