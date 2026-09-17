import os
import tempfile
import unittest
from fap_autonomy.promotion_ledger import PromotionLedger


class PromotionLedgerTests(unittest.TestCase):
    def test_duplicate_trial_not_counted(self):
        with tempfile.TemporaryDirectory() as d:
            l = PromotionLedger(os.path.join(d, "p.sqlite3"))
            kw = dict(trial_id="t1", capability_id="math:x", candidate_digest="abc",
                      success=True, confidence=.9, dev_score=.9, holdout_score=.9,
                      regression_delta=.1, resource_ok=True, holdout_hash="h", evidence_key="e1", evidence={})
            self.assertTrue(l.record_trial(**kw))
            self.assertFalse(l.record_trial(**kw))
            self.assertEqual(l.state("math:x", "abc").verified_trials, 1)

    def test_two_successes_shadow_five_consolidated(self):
        with tempfile.TemporaryDirectory() as d:
            l = PromotionLedger(os.path.join(d, "p.sqlite3"))
            for i in range(5):
                l.record_trial(trial_id=f"t{i}", capability_id="math:x", candidate_digest="abc",
                               success=True, confidence=.9, dev_score=.9, holdout_score=.9,
                               regression_delta=.1, resource_ok=True, holdout_hash="h", evidence_key=f"e{i}", evidence={})
                state = l.state("math:x", "abc")
                if i == 0:
                    self.assertEqual(state.state, "ephemeral")
                if i == 1:
                    self.assertEqual(state.state, "shadow")
            self.assertEqual(l.state("math:x", "abc").state, "consolidated")

    def test_digest_separates_candidate_versions(self):
        with tempfile.TemporaryDirectory() as d:
            l = PromotionLedger(os.path.join(d, "p.sqlite3"))
            l.record_trial(trial_id="t1", capability_id="math:x", candidate_digest="a",
                           success=True, confidence=.9, dev_score=.9, holdout_score=.9,
                           regression_delta=.1, resource_ok=True, holdout_hash="h", evidence_key="ea", evidence={})
            self.assertEqual(l.state("math:x", "b").verified_trials, 0)


if __name__ == "__main__":
    unittest.main()
