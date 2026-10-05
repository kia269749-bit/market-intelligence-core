import unittest
from mi_core.persian_report import build_action

class PersianReportTests(unittest.TestCase):
    def test_bullish_action(self):
        r=build_action([{"symbol":"BTCUSDT","price":100.0}],"BULLISH",0.8)
        self.assertEqual(r["status"],"WATCH_BUY")
        self.assertLess(r["stop"],r["price"])
        self.assertGreater(r["target2"],r["price"])

    def test_neutral_waits(self):
        r=build_action([{"symbol":"BTCUSDT","price":100.0}],"NEUTRAL",0.5)
        self.assertEqual(r["status"],"WAIT")

if __name__=="__main__": unittest.main()
