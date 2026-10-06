import unittest
from unittest.mock import patch
from mi_core.live_brain import _market_bias, print_live, run_once, _data_quality, _microstructure, _fuse

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
        snap={"ts":0,"market":{"rows":[]},"fomo":{"candidates":[]},"evidence":{
            "market":{"bias":"NEUTRAL","confidence":0.5,"sources":1},
            "combined":{"bias":"BULLISH","confidence":0.7,"agreement":1.0,"actionable":True},
            "data_quality":{"status":"SAFE","score":1.0},
            "microstructure":{"divergence":"NONE","squeeze_risk":False},
            "fomo":{"candidates":0,"top":[],"wallet_level":False}}}
        with patch("builtins.print") as p: print_live(snap)
        first=p.call_args_list[1].args[0]
        self.assertIn("market_bias=BULLISH confidence=0.70", first)
        self.assertIn("raw_market_bias=NEUTRAL", first)

    def test_fomo_failure_does_not_fail_cycle(self):
        market={"rows":[{"change_24h_pct":0.0,"price":100}]}
        with patch("mi_core.live_brain.fetch_snapshot", return_value=market), patch("mi_core.live_brain.scan_boosted", side_effect=TimeoutError("fomo timeout")):
            snap=run_once()
        self.assertEqual(snap["evidence"]["combined"]["bias"],"NEUTRAL")
        self.assertTrue(snap["fomo_error"])
        self.assertTrue(snap["research_only"])
        self.assertFalse(snap["live_orders"])

    def test_unsafe_data_blocks_action(self):
        q=_data_quality({"rows":[]})
        self.assertEqual(q["status"],"UNSAFE")
        fused=_fuse([("BULLISH",.9)], q["score"])
        self.assertFalse(fused["actionable"])

    def test_conflicting_microstructure_penalizes_action(self):
        market={"rows":[{"change_24h_pct":5.0,"price":100}]}
        p60={"available":True,"bias":"BULLISH","confidence":.8,
             "assets":{"BTC":{"available":True,"trade_imbalance_pct":-90,"funding":0}}}
        with patch("mi_core.live_brain.fetch_snapshot", return_value=market), patch("mi_core.live_brain.scan_boosted", return_value={"candidates":[] }):
            snap=run_once(project60=p60)
        self.assertEqual(snap["evidence"]["microstructure"]["divergence"],"BEARISH_DIVERGENCE")
        self.assertLess(snap["evidence"]["combined"]["confidence"],.8)

    def test_fusion_disagreement_is_not_actionable(self):
        result=_fuse([("BULLISH",.8),("BEARISH",.8)],1.0)
        self.assertFalse(result["actionable"])
        self.assertEqual(result["bias"],"NEUTRAL")

if __name__=="__main__": unittest.main()
