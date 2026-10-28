import unittest

from tools.validate_protocol_lock import validate_protocol_lock


class ProtocolLockTests(unittest.TestCase):
    def test_protocol_lock_is_explicit_and_fail_closed(self):
        lock = validate_protocol_lock()
        self.assertEqual(lock["execution_cost_policy"]["project_default_round_trip_pct"], 0.24)
        self.assertEqual(lock["execution_cost_policy"]["sensitivity_round_trip_pct"], [0.24, 0.12, 0.04])
        self.assertEqual(lock["historical_periods"]["status"], "RETROSPECTIVE_ONLY_NOT_UNTOUCHED")
        self.assertIn("random_signal_matched_trade_count_seeded", lock["baselines"])
        self.assertTrue(lock["acceptance_criteria"]["require_data_leakage_tests"])


if __name__ == "__main__":
    unittest.main()
