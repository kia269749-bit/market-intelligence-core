import unittest
from mi_core.persian_report import build_action, render_persian

class PersianReportTests(unittest.TestCase):
    def test_bullish_action(self):
        r=build_action([{"symbol":"BTCUSDT","price":100.0}],"BULLISH",0.8)
        self.assertEqual(r["status"],"WATCH_BUY")
        self.assertLess(r["stop"],r["price"])
        self.assertGreater(r["target2"],r["price"])
        self.assertTrue(r["gate"].approved)
        self.assertGreaterEqual(r["gate"].modeled_net_profit_usd,10.0)

    def test_report_uses_combined_bias_and_project60_evidence(self):
        snapshot={"market":{"rows":[{"symbol":"BTCUSDT","price":100.0}]},
                  "evidence":{"market":{"bias":"NEUTRAL","confidence":0.5,"sources":3},
                              "combined":{"bias":"BULLISH","confidence":0.8,"actionable":True},
                              "fomo":{"candidates":1,"wallet_level":False,"top":[]}}}
        project60={"available":True,"bias":"BULLISH","confidence":0.8,
                   "assets":{"BTC":{"available":True,"direction":"BULLISH",
                   "orderbook_imbalance_pct":15.0,"trade_imbalance_pct":25.0,
                   "open_interest":100.0,"funding":0.00001,
                   "evidence":["orderbook_buy_pressure","trade_buy_pressure"]}}}
        report=render_persian(snapshot,project60)
        self.assertIn("تصمیم ترکیبی: BULLISH",report)
        self.assertIn("Project 60: BULLISH",report)
        self.assertIn("فعلاً ورود تأیید نمی‌شود",report)
        self.assertNotIn("نامزد خرید، آماده‌ی ورود پژوهشی",report)
        self.assertIn("گیت اقتصادی عبور نکرده",report)

    def test_report_uses_validated_forecast_levels_not_hardcoded_targets(self):
        snapshot={
            "market":{"rows":[{"symbol":"BTCUSDT","price":100.0}],
                      "data_quality":{"status":"HEALTHY","successful_sources":4,"expected_sources":4}},
            "capital_economics":{"available":True,"approved":True,"expected_move_pct":2.5,
                                 "required_move_pct":1.15,"modeled_profit_usd":10.75,"round_trip_cost_pct":0.35},
            "evidence":{
                "market":{"bias":"BULLISH","confidence":0.8,"sources":4},
                "combined":{"bias":"BULLISH","confidence":0.8,"actionable":True},
                "execution_ready":True,
                "forecast_alignment":{"approved":True,"direction":"BULLISH","state":"ALIGNED","reason":"all gates passed"},
                "no_trade":{"blocked":False,"reasons":[]},
                "timing":{"state":"EARLY","reason":"entry timing passed","remaining_move_pct":2.5},
                "forecast":{"available":True,"asset":"BTC","price":100.0,
                    "selected":{"direction":"UP","expected_return_pct":2.5,"expected_move_pct":2.5,
                                "target_hit_probability":0.7,"horizon":20},
                    "adaptive_validation":{"available":True,"accepted":True,"selected_strategy":"ema_trend",
                        "walk_forward_oos":{"trades":20,"net_profit_pct":12.0,"profit_factor":1.4}}},
                "multi_timeframe":{"available":True,"bias":"BULLISH","score":0.8,"agreement":1.0,
                    "aligned_timeframes":3,"timeframes":{},"structural_target_reference":105.0},
                "fomo":{"candidates":0,"wallet_level":False,"top":[]},
            }
        }
        report=render_persian(snapshot)
        self.assertIn("نامزد خرید، آماده‌ی ورود پژوهشی",report)
        self.assertIn("حد ضرر مدل: 98.7500",report)
        self.assertIn("هدف مدل: 102.5000",report)
        self.assertIn("انتخاب‌گر پویا: EDGE",report)
        self.assertIn("هیچ سفارش واقعی ارسال نمی‌شود",report)

    def test_report_never_suggests_entry_when_data_is_unsafe(self):
        snapshot={"market":{"rows":[{"symbol":"BTCUSDT","price":100.0}],
                            "data_quality":{"status":"UNSAFE"}},
                  "evidence":{"combined":{"bias":"BULLISH","confidence":0.9,"actionable":True},
                              "fomo":{"candidates":0,"wallet_level":False,"top":[]}}}
        report=render_persian(snapshot)
        self.assertIn("کیفیت داده ناامن است",report)
        self.assertNotIn("نامزد خرید، آماده‌ی ورود پژوهشی",report)

    def test_weak_setup_is_blocked(self):
        r=build_action([{"symbol":"BTCUSDT","price":100.0}],"BULLISH",0.65)
        self.assertEqual(r["status"],"WAIT")

    def test_neutral_waits(self):
        r=build_action([{"symbol":"BTCUSDT","price":100.0}],"NEUTRAL",0.5)
        self.assertEqual(r["status"],"WAIT")

if __name__=="__main__": unittest.main()
