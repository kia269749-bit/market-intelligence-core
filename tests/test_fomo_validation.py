import unittest

from mi_core.fomo_validation import FomoValidationEvent, validate_fomo_events


class FomoValidationTests(unittest.TestCase):
    def test_validates_outcomes_and_score_buckets(self):
        events = [
            FomoValidationEvent("e1", "MEME", 100, 100.0, (101.0, 106.0), score=0.90),
            FomoValidationEvent("e2", "MEME", 200, 100.0, (99.0, 94.0), score=0.40),
        ]
        result = validate_fomo_events(events)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["events"], 2)
        self.assertEqual(result["summary"]["target_hit_rate"], 0.5)
        self.assertEqual(result["summary"]["positive_return_rate"], 0.5)
        self.assertEqual(result["score_buckets"]["0.85-1.00"]["events"], 1)
        self.assertEqual(result["score_buckets"]["0.00-0.49"]["events"], 1)

    def test_respects_horizon(self):
        event = FomoValidationEvent("e1", "MEME", 100, 100.0, (106.0, 94.0), score=0.8)
        result = validate_fomo_events([event], horizon=1)
        self.assertEqual(result["summary"]["target_hit_rate"], 1.0)
        self.assertEqual(result["summary"]["stop_hit_rate"], 0.0)

    def test_minimum_sample_gate(self):
        event = FomoValidationEvent("e1", "MEME", 100, 100.0, (101.0,), score=0.8)
        result = validate_fomo_events([event], min_events=3)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["events"], 1)

    def test_rejects_duplicate_event_ids(self):
        event = FomoValidationEvent("e1", "MEME", 100, 100.0, (101.0,), score=0.8)
        with self.assertRaises(ValueError):
            validate_fomo_events([event, event])

    def test_rejects_invalid_confidence(self):
        event = FomoValidationEvent("e1", "MEME", 100, 100.0, (101.0,), trader_confidence=1.2)
        with self.assertRaises(ValueError):
            validate_fomo_events([event])


if __name__ == "__main__":
    unittest.main()
