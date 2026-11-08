import unittest

from mi_core.cost_policy import DEFAULT_COST_POLICY, CostPolicy, resolve_round_trip_cost_pct


class CostPolicyTests(unittest.TestCase):
    def test_v4_base_and_strict_rates(self):
        self.assertEqual(DEFAULT_COST_POLICY.round_trip_pct("base"), 0.15)
        self.assertEqual(DEFAULT_COST_POLICY.round_trip_pct("strict"), 0.45)

    def test_explicit_override_is_separate_scenario(self):
        self.assertEqual(resolve_round_trip_cost_pct("base", override=0.35), 0.35)

    def test_rejects_invalid_policy(self):
        with self.assertRaises(ValueError):
            CostPolicy(base_round_trip_pct=-0.1)
        with self.assertRaises(ValueError):
            CostPolicy(base_round_trip_pct=0.5, strict_round_trip_pct=0.4)

    def test_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            resolve_round_trip_cost_pct("unknown")


if __name__ == "__main__":
    unittest.main()
