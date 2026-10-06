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
                              "combined":{"bias":"BULLISH","confidence":0.8},
                              "fomo":{"candidates":1,"wallet_level":False,"top":[]}}}
        project60={"available":True,"bias":"BULLISH","confidence":0.8,
                   "assets":{"BTC":{"available":True,"direction":"BULLISH",
                   "orderbook_imbalance_pct":15.0,"trade_imbalance_pct":25.0,
                   "open_interest":100.0,"funding":0.00001,
                   "evidence":["orderbook_buy_pressure","trade_buy_pressure"]}}}
        report=render_persian(snapshot,project60)
        self.assertIn("تصمیم ترکیبی: BULLISH",report)
        self.assertIn("Project 60: BULLISH",report)
        self.assertIn("محدوده ورود",report)
        self.assertIn("گیت $10: PASS",report)
        self.assertIn("سود خالص مدل‌شده",report)

    def test_weak_setup_is_blocked(self):
        r=build_action([{"symbol":"BTCUSDT","price":100.0}],"BULLISH",0.65)
        self.assertEqual(r["status"],"WAIT")

    def test_neutral_waits(self):
        r=build_action([{"symbol":"BTCUSDT","price":100.0}],"NEUTRAL",0.5)
        self.assertEqual(r["status"],"WAIT")

if __name__=="__main__": unittest.main()
