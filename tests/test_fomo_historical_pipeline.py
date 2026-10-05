import json
import tempfile
import unittest
from pathlib import Path

from tools.fomo_historical_pipeline import run


class FomoHistoricalPipelineTests(unittest.TestCase):
    def test_builds_normalized_and_ranked_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / "raw"
            raw.mkdir()
            rows = []
            for i in range(3):
                rows.append({
                    "captured_at": 100 + i,
                    "payload": {
                        "traders": [{
                            "rank": 1,
                            "userId": "u1",
                            "handle": "alpha",
                            "displayName": "Alpha",
                            "pnlUsd": 100 + i * 10,
                            "volumeUsd": 1000,
                            "trades": 5,
                            "followers": 2,
                            "holdings": 1,
                            "wallets": 1,
                            "verified": True,
                        }]
                    },
                })
            (raw / "leaderboard_7d.jsonl").write_text(
                "".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8"
            )
            normalized = root / "normalized" / "snapshots.jsonl"
            rankings = root / "reports" / "ranking.jsonl"
            result = run(raw, normalized, rankings, 3)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["trader_id"], "u1")
            self.assertEqual(len(normalized.read_text().splitlines()), 3)
            self.assertEqual(len(rankings.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
