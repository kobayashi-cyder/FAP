import unittest
from fap_autonomy.models import CapabilityCandidate, GapType
from fap_autonomy.priority_engine import CapabilityPriorityEngine


class PriorityEngineTests(unittest.TestCase):
    def candidate(self, cid, frequency, generality, cost=16, existing=None):
        return CapabilityCandidate(
            cid, GapType.MATH_GAP, ("general",), frequency, 1.0, 0.5, 0.8, generality,
            cost, 4, 3, 0.04, existing_skill_match=existing,
        )

    def test_not_failure_count_only(self):
        engine = CapabilityPriorityEngine()
        frequent_narrow = self.candidate("frequent_narrow", 0.60, 0.10, cost=200)
        moderate_general = self.candidate("moderate_general", 0.35, 0.95, cost=12)
        ranked = engine.rank([frequent_narrow, moderate_general])
        self.assertEqual(ranked[0].candidate.capability_id, "moderate_general")

    def test_existing_skill_penalty(self):
        engine = CapabilityPriorityEngine()
        a = self.candidate("a", 0.4, 0.8, existing="math_skill")
        b = self.candidate("b", 0.4, 0.8, existing=None)
        self.assertGreater(engine.score(b).score, engine.score(a).score)


if __name__ == "__main__":
    unittest.main()
