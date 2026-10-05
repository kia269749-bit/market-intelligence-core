import json
import tempfile
import unittest
from pathlib import Path

from mi_core.fomo_history_store import load_snapshots, write_rankings
from mi_core.fomo_normalizer import FomoTraderSnapshot


class FomoHistoryStoreTests(unittest.TestCase):
    def test_round_trip_and_ranking_output(self):
        snapshots = [
            FomoTraderSnapshot("7d", i + 1, "u1", "alpha", "Alpha", 100 + i, 1000 + i * 10, 50000, 20, 5, 2, 1, True)
            for i in range(3)
        ]
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "snapshots.jsonl"
            raw.write_text(
                "".join(json.dumps(s.to_dict()) + "\n" for s in snapshots),
                encoding="utf-8",
            )
            loaded = load_snapshots(raw)
            out = Path(td) / "rankings.jsonl"
            ranked = write_rankings(loaded, out)
            self.assertEqual(len(loaded), 3)
            self.assertEqual(ranked[0]["trader_id"], "u1")
            self.assertTrue(out.exists())
            self.assertEqual(len(out.read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
