import unittest

from deterministic_replay import build_trace, verify_replay


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"observation": {"screen": "home", "count": 1}, "decision": {"kind": "tap"}, "action": {"x": 10, "y": 20}, "random_seed": 7},
            {"observation": {"screen": "done", "count": 2}, "decision": {"kind": "stop"}, "action": {}, "random_seed": 7},
        ]

    def test_deterministic_digest(self):
        a = build_trace(self.rows).digest()
        b = build_trace(list(self.rows)).digest()
        self.assertEqual(a, b)
        self.assertTrue(verify_replay(a, self.rows))

    def test_change_is_detected(self):
        digest = build_trace(self.rows).digest()
        changed = [dict(x) for x in self.rows]
        changed[0] = dict(changed[0])
        changed[0]["action"] = {"x": 11, "y": 20}
        self.assertFalse(verify_replay(digest, changed))


if __name__ == "__main__":
    unittest.main()
