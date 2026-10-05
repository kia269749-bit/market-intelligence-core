import tempfile
import unittest
from pathlib import Path
from mi_core.fomo_outcome_store import append_outcome, load_outcomes

class FomoOutcomeStoreTests(unittest.TestCase):
    def test_append_only_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"outcomes.jsonl"
            append_outcome(path, {"event_id":"e1","return_pct":8.5})
            append_outcome(path, {"event_id":"e2","return_pct":-2.0})
            rows=load_outcomes(path)
            self.assertEqual([r["event_id"] for r in rows], ["e1","e2"])
            self.assertEqual(rows[0]["return_pct"], 8.5)

if __name__ == "__main__":
    unittest.main()
