import unittest

from fap_goal_loop.staged_canary import BoundedStagedCanary, CanaryObservation


def obs(key, digest="abc", success=True, quality=0.1, latency=1.0):
    return CanaryObservation(key, digest, success, quality, latency)


class StagedCanaryTests(unittest.TestCase):
    def test_stage_evidence_is_isolated_and_bounded(self):
        canary = BoundedStagedCanary("abc", min_evidence=2, min_success_rate=1.0)
        self.assertEqual(canary.add(obs("a")), "monitoring")
        self.assertEqual(canary.add(obs("b")), "advanced")
        self.assertEqual(canary.stage, 0.20)
        self.assertEqual(canary.evaluate(), "monitoring")

    def test_regression_requests_rollback_without_executing_it(self):
        canary = BoundedStagedCanary("abc", min_evidence=2, min_success_rate=1.0)
        canary.add(obs("a"))
        self.assertEqual(canary.add(obs("b", success=False)), "rollback")
        self.assertFalse(hasattr(canary, "execute"))
        self.assertFalse(hasattr(canary, "verified"))
        self.assertFalse(hasattr(canary, "completed"))

    def test_latency_regression_requests_rollback(self):
        canary = BoundedStagedCanary("abc", min_evidence=2, max_latency_ratio=1.25)
        canary.add(obs("a", latency=1.0))
        self.assertEqual(canary.add(obs("b", latency=1.5)), "rollback")

    def test_duplicate_evidence_cannot_fill_stage(self):
        canary = BoundedStagedCanary("abc", min_evidence=2)
        self.assertEqual(canary.add(obs("same")), "monitoring")
        self.assertEqual(canary.add(obs("same")), "monitoring")
        self.assertEqual(canary.stage, 0.05)

    def test_invalid_or_cross_candidate_evidence_fails_closed(self):
        with self.assertRaises(ValueError):
            BoundedStagedCanary("")
        with self.assertRaises(ValueError):
            BoundedStagedCanary("abc", min_success_rate=1.1)
        canary = BoundedStagedCanary("abc", min_evidence=1)
        with self.assertRaises(ValueError):
            canary.add(obs("x", digest="other"))
        with self.assertRaises(ValueError):
            canary.add(obs("x", latency=0.0))


if __name__ == "__main__":
    unittest.main()
