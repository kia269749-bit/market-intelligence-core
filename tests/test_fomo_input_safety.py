import math
import unittest

from mi_core.fomo_direction import infer_direction
from mi_core.fomo_leader_follower import (
    TraderFill,
    detect_leader_follower_events,
)


class FomoInputSafetyTests(unittest.TestCase):
    def fills(self, leader_confidence=1.0, follower_two_amount=40.0):
        return [
            TraderFill("LEADER", "MEME", 100, "BUY", 100.0, leader_confidence),
            TraderFill("FOLLOWER1", "MEME", 110, "BUY", 50.0, 0.95),
            TraderFill("FOLLOWER2", "MEME", 120, "BUY", follower_two_amount, 0.95),
        ]

    def test_conflicting_direction_evidence_is_not_reliable(self):
        result = infer_direction(
            target_token_delta=1.0,
            quote_token_delta=-1.0,
            dex_direction="SELL",
        )
        self.assertEqual(result["direction"], "UNKNOWN")
        self.assertFalse(result["reliable"])

    def test_nan_leader_score_cannot_create_a_leader_event(self):
        events = detect_leader_follower_events(
            self.fills(), {"LEADER": math.nan}, min_followers=2
        )
        self.assertEqual(events, [])

    def test_nonfinite_leader_confidence_is_rejected(self):
        events = detect_leader_follower_events(
            self.fills(leader_confidence=math.nan), {"LEADER": 0.95}, min_followers=2
        )
        self.assertEqual(events, [])

    def test_nonfinite_follower_amount_is_rejected(self):
        events = detect_leader_follower_events(
            self.fills(follower_two_amount=math.nan), {"LEADER": 0.95}, min_followers=2
        )
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
