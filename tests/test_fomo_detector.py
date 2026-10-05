import unittest

from mi_core.fomo_detector import detect_fomo_event


class FomoDetectorTests(unittest.TestCase):
    def test_no_event_without_abnormal_volume(self):
        self.assertIsNone(
            detect_fomo_event("DOGE", 1, [100, 105, 95, 100], 105)
        )

    def test_event_on_abnormal_volume(self):
        event = detect_fomo_event("DOGE", 2, [100, 105, 95, 100], 250)
        self.assertIsNotNone(event)
        self.assertTrue(event.abnormal_volume)
        self.assertGreaterEqual(event.volume_z, 2.0)

    def test_persistence_only_enhances_score(self):
        base = detect_fomo_event("DOGE", 3, [100, 105, 95, 100], 250, trader_persistence=0)
        strong = detect_fomo_event("DOGE", 3, [100, 105, 95, 100], 250, trader_persistence=1)
        self.assertIsNotNone(base)
        self.assertIsNotNone(strong)
        self.assertGreater(strong.score, base.score)


if __name__ == "__main__":
    unittest.main()
