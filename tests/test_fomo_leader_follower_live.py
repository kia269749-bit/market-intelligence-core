import json,tempfile,unittest
from pathlib import Path
from mi_core.fomo_leader_follower_live import summarize
class TestFomoLeaderFollowerLive(unittest.TestCase):
    def test_cluster_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"fills.jsonl"; s=Path(d)/"scores.json"
            rows=[
              {"trader_id":"L","token":"MEME","timestamp":100,"direction":"BUY","amount_usd":1000,"confidence":.9},
              {"trader_id":"F1","token":"MEME","timestamp":110,"direction":"BUY","amount_usd":500,"confidence":.9},
              {"trader_id":"F2","token":"MEME","timestamp":120,"direction":"BUY","amount_usd":400,"confidence":.9}]
            p.write_text("\n".join(json.dumps(x) for x in rows)+"\n")
            s.write_text(json.dumps({"L":.9}))
            r=summarize(str(p),str(s))
            self.assertTrue(r["confirmed"]); self.assertEqual(r["events"][0]["follower_count"],2)
if __name__=="__main__":unittest.main()
