import unittest
from fap_autonomy.models import LifecycleRecord
from fap_autonomy.lifecycle import VerificationLifecycle


class LifecycleTests(unittest.TestCase):
    def test_progression_requires_repetition(self):
        lc = VerificationLifecycle()
        r = LifecycleRecord("x")
        lc.observe(r, success=True, confidence=0.9, dev_score=0.8, holdout_score=0.8,
                   regression_delta=0, resource_ok=True)
        self.assertEqual(r.state, "ephemeral")
        lc.observe(r, success=True, confidence=0.9, dev_score=0.8, holdout_score=0.8,
                   regression_delta=0, resource_ok=True)
        self.assertEqual(r.state, "shadow")
        for _ in range(3):
            lc.observe(r, success=True, confidence=0.9, dev_score=0.8, holdout_score=0.8,
                       regression_delta=0, resource_ok=True)
        self.assertEqual(r.state, "consolidated")

    def test_regression_blocks_promotion(self):
        lc = VerificationLifecycle()
        r = LifecycleRecord("x")
        for _ in range(5):
            lc.observe(r, success=True, confidence=0.95, dev_score=0.8, holdout_score=0.8,
                       regression_delta=-0.3, resource_ok=True)
        self.assertNotEqual(r.state, "consolidated")


if __name__ == "__main__":
    unittest.main()
