import unittest

from evidence_retention import EvidenceRef, plan_retention


class RetentionTests(unittest.TestCase):
    def test_keeps_recent_and_protected(self):
        rows = [
            EvidenceRef("a1", "cap-a", 1),
            EvidenceRef("a2", "cap-a", 2),
            EvidenceRef("a3", "cap-a", 3),
            EvidenceRef("b1", "cap-b", 1),
            EvidenceRef("b2", "cap-b", 2, protected=True),
        ]
        plan = plan_retention(rows, keep_latest_per_capability=1, protected_ids=["a1"])
        self.assertEqual(set(plan.keep_ids), {"a1", "a3", "b2"})
        self.assertEqual(set(plan.compact_ids), {"a2", "b1"})

    def test_is_deterministic(self):
        rows = [EvidenceRef("x1", "x", 1), EvidenceRef("x2", "x", 2)]
        a = plan_retention(rows, keep_latest_per_capability=1)
        b = plan_retention(reversed(rows), keep_latest_per_capability=1)
        self.assertEqual(a, b)

    def test_duplicate_id_rejected(self):
        with self.assertRaises(ValueError):
            plan_retention([EvidenceRef("x", "a", 1), EvidenceRef("x", "b", 2)], keep_latest_per_capability=1)


if __name__ == "__main__":
    unittest.main()
