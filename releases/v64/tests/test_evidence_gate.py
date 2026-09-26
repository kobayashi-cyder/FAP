import unittest
from fap_autonomy.evidence_gate import EvidenceGate, EvidencePolicy
from fap_autonomy.models import FailureCluster, GapType, CapabilityCandidate, PriorityDecision


class EvidenceGateTests(unittest.TestCase):
    def _decision(self, score=1.0):
        c = CapabilityCandidate("math", GapType.MATH_GAP, ("general",), 0.2, 0.5, 0.3, 0.8, 0.8, 10, 2, 1, 0.05)
        return PriorityDecision(c, 1.0, 1.0, score, ("test",))

    def test_small_sample_is_deferred(self):
        c = FailureCluster("MATH_GAP/general", GapType.MATH_GAP, ("general",), count=2,
                           successes_in_family=1, total_in_family=3)
        d = EvidenceGate().evaluate(verified_cases=4, cluster=c, priority=self._decision())
        self.assertFalse(d.ready)
        self.assertIn("verified_cases", d.reason)

    def test_sufficient_repeated_evidence_is_ready(self):
        c = FailureCluster("MATH_GAP/general", GapType.MATH_GAP, ("general",), count=6,
                           successes_in_family=14, total_in_family=20)
        d = EvidenceGate().evaluate(verified_cases=25, cluster=c, priority=self._decision())
        self.assertTrue(d.ready)
