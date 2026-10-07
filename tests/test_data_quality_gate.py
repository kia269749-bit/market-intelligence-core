import unittest
from mi_core.live_brain import run_once

class TestDataQualityGate(unittest.TestCase):
    def _base(self, status):
        return {
            "rows":[{"symbol":"BTCUSDT","price":100.0,"change_24h_pct":1.0}],
            "data_quality":{
                "status":status,
                "score":1.0 if status=="HEALTHY" else 0.65 if status=="DEGRADED" else 0.0,
                "successful_sources":1,"expected_sources":1,
            },
        }

    def test_healthy_allows_normal_pipeline(self):
        import mi_core.live_brain as lb
        original=lb.fetch_snapshot
        try:
            lb.fetch_snapshot=lambda symbols, exchanges:self._base("HEALTHY")
            lb.scan_boosted=lambda chain,limit: {"candidates":[]}
            out=run_once(symbols=["BTCUSDT"], exchanges=[])
            self.assertEqual(out["evidence"]["market_data_gate"],"HEALTHY")
        finally:
            lb.fetch_snapshot=original

    def test_degraded_is_watch_only(self):
        import mi_core.live_brain as lb
        original=lb.fetch_snapshot
        try:
            lb.fetch_snapshot=lambda symbols, exchanges:self._base("DEGRADED")
            lb.scan_boosted=lambda chain,limit: {"candidates":[]}
            out=run_once(symbols=["BTCUSDT"], exchanges=[])
            self.assertEqual(out["evidence"]["market_data_gate"],"DEGRADED")
            self.assertFalse(out["evidence"]["combined"]["actionable"])
            self.assertIn("degraded_data_watch_only",out["evidence"]["no_trade"]["reasons"])
        finally:
            lb.fetch_snapshot=original

    def test_unsafe_forces_wait(self):
        import mi_core.live_brain as lb
        original=lb.fetch_snapshot
        try:
            lb.fetch_snapshot=lambda symbols, exchanges:self._base("UNSAFE")
            lb.scan_boosted=lambda chain,limit: {"candidates":[]}
            out=run_once(symbols=["BTCUSDT"], exchanges=[])
            self.assertEqual(out["evidence"]["market_data_gate"],"UNSAFE")
            self.assertFalse(out["evidence"]["combined"]["actionable"])
            self.assertEqual(out["evidence"]["combined"]["confidence"],0.0)
        finally:
            lb.fetch_snapshot=original

if __name__=="__main__":
    unittest.main()
