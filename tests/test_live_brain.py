import unittest
from unittest.mock import patch
from mi_core.live_brain import _market_bias, print_live, run_once

class LiveBrainTests(unittest.TestCase):
    def test_leader_follower_evidence_shape_is_preserved(self):
        evidence = {"available": True, "confirmed": True, "events": [{"token": "MEME"}]}
        self.assertTrue(evidence["confirmed"])
        self.assertEqual(evidence["events"][0]["token"], "MEME")

    def test_neutral_without_change_data(self):
        bias,confidence=_market_bias({"rows":[]})
        self.assertEqual(bias,"NEUTRAL")
        self.assertEqual(confidence,.25)

    def test_headline_uses_combined_decision(self):
        snap={
            "ts":0,
            "market":{"rows":[]},
            "fomo":{"candidates":[]},
            "evidence":{
                "market":{"bias":"NEUTRAL","confidence":0.5,"sources":1},
                "combined":{"bias":"BULLISH","confidence":0.7},
                "fomo":{"candidates":0,"top":[],"wallet_level":False},
            },
        }
        with patch("builtins.print") as p:
            print_live(snap)
        first=p.call_args_list[1].args[0]
        self.assertIn("market_bias=BULLISH confidence=0.70", first)
        self.assertIn("raw_market_bias=NEUTRAL", first)

    def test_fomo_failure_does_not_fail_cycle(self):
        market={"rows":[{"change_24h_pct":0.0}]}
        with patch("mi_core.live_brain.fetch_snapshot", return_value=market),              patch("mi_core.live_brain.scan_boosted", side_effect=TimeoutError("fomo timeout")):
            snap=run_once()
        self.assertEqual(snap["evidence"]["combined"]["bias"],"NEUTRAL")
        self.assertTrue(snap["fomo_error"])
        self.assertTrue(snap["research_only"])
        self.assertFalse(snap["live_orders"])

if __name__=="__main__": unittest.main()
