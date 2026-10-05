import unittest
from mi_core.fomo_live_monitor import dedupe_events, parse_alert

class FomoLiveMonitorTests(unittest.TestCase):
    def test_parse_buy_alert(self):
        event = parse_alert({"type":"alert","alertType":"buy","eventId":"e1","userId":"u1","trader":"winner","token":"MEME","tokenAddress":"0xabc","chain":"base","usdValue":4200,"ts":1000,"tradeId":"t1"})
        self.assertEqual(event.action, "BUY")
        self.assertEqual(event.trader_id, "u1")
        self.assertEqual(event.usd_value, 4200)

    def test_ignores_non_trade_alerts(self):
        self.assertIsNone(parse_alert({"type":"alert","alertType":"thesis","eventId":"e1","userId":"u1"}))

    def test_dedupes_by_event_id(self):
        payload={"type":"alert","alertType":"sell","eventId":"e1","userId":"u1","trader":"x","token":"M","tokenAddress":"a","chain":"solana","usdValue":100,"ts":1}
        event=parse_alert(payload)
        self.assertEqual(len(dedupe_events([event,event])), 1)

if __name__ == "__main__":
    unittest.main()
