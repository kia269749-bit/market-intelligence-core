import unittest
from mi_core.fomo_direction import TradeDirection
from mi_core.fomo_leader_follower import TraderFill, detect_leader_follower_events

class LeaderFollowerTests(unittest.TestCase):
    def test_detects_cluster(self):
        fills = [
            TraderFill("leader","MEME",100,TradeDirection.BUY,18000,.95),
            TraderFill("f1","MEME",110,TradeDirection.BUY,7000,.90),
            TraderFill("f2","MEME",125,TradeDirection.BUY,5000,.90),
            TraderFill("other","MEME",700,TradeDirection.BUY,9000,.90),
        ]
        events = detect_leader_follower_events(fills, {"leader":.90}, min_followers=2)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].leader_id, "leader")
        self.assertEqual(events[0].follower_count, 2)
        self.assertEqual(events[0].follower_volume_usd, 12000.0)
    def test_unknown_direction_is_not_causal(self):
        fills = [
            TraderFill("leader","MEME",100,TradeDirection.UNKNOWN,18000,.95),
            TraderFill("f1","MEME",110,TradeDirection.BUY,7000,.90),
            TraderFill("f2","MEME",125,TradeDirection.BUY,5000,.90),
        ]
        self.assertEqual(detect_leader_follower_events(fills, {"leader":.90}, min_followers=2), [])

if __name__ == "__main__": unittest.main()
