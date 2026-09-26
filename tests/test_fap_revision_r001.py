import math
import unittest

from fap_revision_r001 import Signal, adaptive_budget, needs_extra_path


class RevisionR001Tests(unittest.TestCase):
    def test_baseline_is_sparse(self):
        budget = adaptive_budget()
        self.assertEqual(budget.routes, 1)
        self.assertEqual(budget.verify, 1)

    def test_difficulty_increases_bounded_compute(self):
        base = adaptive_budget()
        hard = adaptive_budget(
            [Signal("multi_step", 0.9, 5), Signal("verification", 0.8, 3)],
            uncertainty=0.8,
            disagreement=True,
        )
        self.assertGreaterEqual(hard.routes, base.routes)
        self.assertGreaterEqual(hard.steps, base.steps)
        self.assertGreaterEqual(hard.verify, base.verify)
        self.assertLessEqual(hard.routes, 8)
        self.assertLessEqual(hard.steps, 96)
        self.assertLessEqual(hard.verify, 6)
        self.assertLessEqual(hard.retries, 4)

    def test_sparse_to_dense_trigger(self):
        self.assertFalse(needs_extra_path(confidence=0.95))
        self.assertTrue(needs_extra_path(confidence=0.60))
        self.assertTrue(needs_extra_path(confidence=0.95, disagreement=True))
        self.assertTrue(needs_extra_path(confidence=0.95, counterexample=True))

    def test_non_finite_confidence_fails_toward_verification(self):
        self.assertTrue(needs_extra_path(confidence=math.nan))
        self.assertTrue(needs_extra_path(confidence=math.inf))
        self.assertTrue(needs_extra_path(confidence=-math.inf))

    def test_non_finite_uncertainty_cannot_expand_compute(self):
        base = adaptive_budget()
        self.assertEqual(adaptive_budget(uncertainty=math.nan), base)
        self.assertEqual(adaptive_budget(uncertainty=math.inf), base)

    def test_malformed_signal_values_are_bounded(self):
        budget = adaptive_budget([
            Signal("bad-weight", math.nan, 8),
            Signal("bad-count", 1.0, math.inf),
            Signal("huge-count", 1.0, 10**12),
        ])
        self.assertLessEqual(budget.routes, 8)
        self.assertLessEqual(budget.steps, 96)
        self.assertLessEqual(budget.verify, 6)
        self.assertLessEqual(budget.retries, 4)

    def test_none_and_non_signal_entries_do_not_crash(self):
        self.assertEqual(adaptive_budget(None), adaptive_budget())
        mixed = adaptive_budget([None, object(), Signal("ok", 0.5, 2)])
        self.assertIsInstance(mixed.routes, int)


if __name__ == "__main__":
    unittest.main()
