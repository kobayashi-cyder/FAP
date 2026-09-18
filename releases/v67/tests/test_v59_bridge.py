import unittest
from fap_autonomy.v59_bridge import V59OutcomeAdapter


class V59BridgeTests(unittest.TestCase):
    def test_unverified_turn_is_excluded(self):
        rows = [{"id": "1", "text": "hello", "intent": "chat", "skills": ["memory"]}]
        self.assertEqual(V59OutcomeAdapter.verified_results(rows), [])

    def test_verify_bad_becomes_failure(self):
        rows = [{
            "id": "2", "text": "solve multi-step percentage word problem", "intent": "math",
            "skills": ["math", "reason"], "feedback": "bad", "teacher_used": True,
        }]
        out = V59OutcomeAdapter.verified_results(rows)
        self.assertEqual(len(out), 1)
        self.assertFalse(out[0].success)
        self.assertTrue(out[0].verified)
        self.assertTrue(out[0].teacher_used)

    def test_verify_good_becomes_success(self):
        rows = [{
            "turn_id": "3", "request_text": "why control unstable", "intent": "science",
            "selected_skills": ["knowledge", "science", "reason"], "verify_feedback": "good",
        }]
        out = V59OutcomeAdapter.verified_results(rows)
        self.assertTrue(out[0].success)
        self.assertEqual(out[0].metadata["selected_skills"], ["knowledge", "science", "reason"])


if __name__ == "__main__":
    unittest.main()
