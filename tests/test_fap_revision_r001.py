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


if __name__ == "__main__":
    unittest.main()
