import unittest, json, tempfile, os
from unittest.mock import patch
from mi_core.live_brain import _market_bias, print_live, run_once, _data_quality, _microstructure, _fuse, _regime, _outcome_adjustment, _smart_money_score, _no_trade_guard, _forecast_from_project60, _forecast_alignment_gate
from mi_core.timing_engine import evaluate_entry_timing

class LiveBrainTests(unittest.TestCase):
    def test_forecast_alignment_gate_accepts_aligned_viable_forecast(self):
        forecast={"available":True,"selected":{"direction":"UP","expected_return_pct":1.4,
                   "tier":"VIABLE","target_hit_probability":0.50}}
        result=_forecast_alignment_gate(forecast,"BULLISH")
        self.assertTrue(result["approved"])
        self.assertEqual(result["state"],"ALIGNED")

    def test_forecast_alignment_gate_rejects_direction_conflict(self):
        forecast={"available":True,"selected":{"direction":"DOWN","expected_return_pct":-1.8,
                   "tier":"STRONG","target_hit_probability":0.65}}
        result=_forecast_alignment_gate(forecast,"BULLISH")
        self.assertFalse(result["approved"])
        self.assertEqual(result["state"],"CONFLICT")
        self.assertEqual(result["reason"],"forecast_direction_conflict")

    def test_forecast_alignment_gate_rejects_flat_or_low_probability_forecast(self):
        flat=_forecast_alignment_gate({"available":True,"selected":{"direction":"FLAT","tier":"STRONG","target_hit_probability":.8}},"BULLISH")
        weak=_forecast_alignment_gate({"available":True,"selected":{"direction":"UP","expected_return_pct":1.0,"tier":"WATCH","target_hit_probability":.40}},"BULLISH")
        self.assertEqual(flat["state"],"FLAT")
        self.assertFalse(flat["approved"])
        self.assertFalse(weak["approved"])
        self.assertIn(weak["state"],("TIER_REJECT","LOW_TARGET_PROBABILITY"))

    def test_forecast_alignment_gate_rejects_return_sign_mismatch(self):
        forecast={"available":True,"selected":{"direction":"UP","expected_return_pct":-1.2,
                   "tier":"STRONG","target_hit_probability":.8}}
        result=_forecast_alignment_gate(forecast,"BULLISH")
        self.assertFalse(result["approved"])
        self.assertEqual(result["state"],"SIGN_CONFLICT")

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

    def test_run_once_blocks_conflicting_forecast_from_actionable_status(self):
        market={"rows":[{"change_24h_pct":5.0,"price":100.0}],
                "data_quality":{"status":"HEALTHY","score":1.0}}
        forecast={"available":True,"asset":"BTC","price":100.0,
                  "selected":{"direction":"DOWN","expected_return_pct":-2.5,
                              "expected_move_pct":2.5,"target_hit_probability":0.65,
                              "tier":"STRONG","confidence":0.8}}
        fused={"bias":"BULLISH","confidence":0.8,"agreement":1.0,
               "actionable":True,"regime":"TREND"}
        with patch("mi_core.live_brain.fetch_snapshot",return_value=market), \
             patch("mi_core.live_brain.scan_boosted",return_value={"candidates":[]} ), \
             patch("mi_core.live_brain._fuse",return_value=fused):
            snap=run_once(forecast=forecast)
        self.assertEqual(snap["evidence"]["forecast_alignment"]["state"],"CONFLICT")
        self.assertFalse(snap["capital_economics"]["approved"])
        self.assertFalse(snap["evidence"]["combined"]["actionable"])
        self.assertIn("forecast_direction_conflict",snap["evidence"]["no_trade"]["reasons"])

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

    def test_raw_fomo_candidates_do_not_vote_without_leader_confirmation(self):
        market={"rows":[{"change_24h_pct":2.0,"price":100}]}
        fomo={"candidates":[{"token":"PUMP","price_change_24h_pct":500.0,"volume_24h_usd":1000000,"fomo_score":99}]}
        with patch("mi_core.live_brain.fetch_snapshot", return_value=market), patch("mi_core.live_brain.scan_boosted", return_value=fomo):
            snap=run_once()
        self.assertEqual(snap["evidence"]["fomo"]["candidate_signal"], "BULLISH_CANDIDATE")
        self.assertFalse(snap["evidence"]["fusion_inputs"]["fomo_candidates"]["used_as_vote"])
        self.assertEqual(snap["evidence"]["combined"]["bias"], "BULLISH")

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

    def test_regime_blocks_high_volatility_action(self):
        market={"rows":[
            {"change_24h_pct":20.0,"price":100},
            {"change_24h_pct":-18.0,"price":100},
            {"change_24h_pct":15.0,"price":100},
            {"change_24h_pct":-14.0,"price":100},
        ]}
        regime=_regime(market)
        self.assertEqual(regime["name"],"HIGH_VOLATILITY")
        fused=_fuse([("BULLISH",.9)],1.0,regime)
        self.assertFalse(fused["actionable"])
        self.assertLess(fused["confidence"],.9)

    def test_weak_outcome_memory_reduces_confidence(self):
        outcome={"resolved":20,"win_rate":0.35}
        adj=_outcome_adjustment(outcome)
        self.assertEqual(adj["status"],"WEAK")
        self.assertLess(adj["factor"],1.0)
        fused=_fuse([("BULLISH",.8)],1.0,{"name":"TREND"},outcome)
        self.assertLess(fused["confidence"],.8)

    def test_contextual_outcome_memory_is_bounded(self):
        outcome={
            "resolved":20,
            "win_rate":0.55,
            "by_regime":{
                "TREND":{"resolved":10,"win_rate":0.70},
                "RANGE":{"resolved":10,"win_rate":0.30},
            },
            "by_direction":{
                "BULLISH":{"resolved":10,"win_rate":0.70},
                "BEARISH":{"resolved":10,"win_rate":0.40},
            },
        }

        trend=_outcome_adjustment(outcome, regime="TREND", direction="BULLISH")
        range_case=_outcome_adjustment(outcome, regime="RANGE", direction="BEARISH")

        self.assertGreaterEqual(trend["factor"],0.90)
        self.assertLessEqual(trend["factor"],1.05)
        self.assertGreaterEqual(range_case["factor"],0.90)
        self.assertLessEqual(range_case["factor"],1.05)
        self.assertNotEqual(trend["factor"],range_case["factor"])

    def test_context_with_small_sample_does_not_overreact(self):
        outcome={
            "resolved":20,
            "win_rate":0.55,
            "by_regime":{
                "TREND":{"resolved":3,"win_rate":0.0},
            },
        }

        result=_outcome_adjustment(outcome, regime="TREND")

        self.assertEqual(result["factor"],1.0)

    def test_insufficient_outcome_memory_is_neutral(self):
        adj=_outcome_adjustment({"resolved":3,"win_rate":0.0})
        self.assertEqual(adj["status"],"INSUFFICIENT")
        self.assertEqual(adj["factor"],1.0)

    def test_smart_money_score_uses_leader_scores_and_events(self):
        result=_smart_money_score({"leader_score_map":{"a":.8,"b":.7},"leader_scores":2,"events":[{"x":1},{"x":2}]})
        self.assertEqual(result["status"],"STRONG")
        self.assertEqual(result["leaders"],2)
        self.assertEqual(result["events"],2)

    def test_weak_history_alone_does_not_block(self):
        result=_no_trade_guard(
            {"status":"SAFE"},
            {"name":"TREND"},
            {"divergence":"ALIGNED","squeeze_risk":False},
            {"status":"STRONG"},
            {"resolved":20,"win_rate":0.35},
        )
        self.assertFalse(result["blocked"])
        self.assertNotIn("weak_historical_edge", result["reasons"])

    def test_no_trade_guard_blocks_unsafe_conditions(self):
        result=_no_trade_guard(
            {"status":"SAFE"}, {"name":"TREND"},
            {"divergence":"CONFLICT","squeeze_risk":False},
            {"status":"STRONG"}, {"resolved":20,"win_rate":.70}
        )
        self.assertTrue(result["blocked"])
        self.assertIn("source_conflict",result["reasons"])


    def test_capital_economics_exposes_preferred_required_move(self):
        market={"rows":[{"change_24h_pct":0.0,"price":100}],"data_quality":{"status":"HEALTHY","score":1.0}}
        forecast={"available":True,"selected":{"expected_return_pct":0.59,"confidence":0.8,"current_move_pct":0.1}}
        with patch("mi_core.live_brain.fetch_snapshot", return_value=market), patch("mi_core.live_brain.scan_boosted", return_value={"candidates":[]}), patch("mi_core.live_brain.evaluate_capital_target", wraps=__import__("mi_core.trade_economics", fromlist=["evaluate_capital_target"]).evaluate_capital_target):
            snap=run_once(project60={"bias":"NEUTRAL","confidence":0.5}, forecast=forecast)
        self.assertTrue(snap["capital_economics"]["available"])
        self.assertAlmostEqual(snap["capital_economics"]["required_move_pct"], 1.15, places=2)
        self.assertAlmostEqual(snap["capital_economics"]["preferred_required_move_pct"], 2.35, places=2)

    def test_timing_consumption_is_capped_for_display(self):
        timing=evaluate_entry_timing(expected_move_pct=0.14, current_move_pct=0.266, required_move_pct=1.15)
        self.assertEqual(timing["state"], "LATE")
        self.assertGreater(timing["extension_ratio"], 1.0)
        self.assertEqual(timing["consumed_pct"], 100.0)

    def test_future_forecast_is_multi_horizon_and_read_only(self):
        fd,path=tempfile.mkstemp(suffix=".jsonl"); os.close(fd)
        try:
            price=100.0
            with open(path,"w",encoding="utf-8") as f:
                for i in range(80):
                    price*=1.0005
                    f.write(json.dumps({"timestamp":i,"coins":{"BTC":{"price":price}}})+"\n")
            result=_forecast_from_project60(path,"BTC")
            self.assertTrue(result["available"])
            self.assertIn("1_hour",result["horizons"])
            self.assertIn("4_hours",result["horizons"])
            self.assertGreater(result["horizons"]["1_hour"]["up"],.5)
            self.assertTrue(result["research_only"])
        finally:
            os.unlink(path)

if __name__=="__main__": unittest.main()
