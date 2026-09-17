import random
import unittest

from deterministic_replay import build_trace
from replay_runner import run_replay, trace_chain_digest


class ReplayRunnerTests(unittest.TestCase):
    def _trace(self):
        rows = []
        for index, seed in enumerate((11, 22, 33)):
            rng = random.Random(seed)
            value = rng.randint(0, 1000)
            rows.append(
                {
                    "observation": {"screen": f"s{index}", "value": index},
                    "decision": {"score": value, "route": "tap" if value % 2 else "wait"},
                    "action": {"kind": "tap", "x": value % 100, "y": index},
                    "random_seed": seed,
                }
            )
        return build_trace(rows)

    @staticmethod
    def deterministic_executor(observation, seed, index):
        rng = random.Random(seed)
        value = rng.randint(0, 1000)
        return (
            {"score": value, "route": "tap" if value % 2 else "wait"},
            {"kind": "tap", "x": value % 100, "y": index},
        )

    def test_exact_replay_matches(self):
        trace = self._trace()
        result = run_replay(trace, self.deterministic_executor)
        self.assertTrue(result.matched)
        self.assertIsNone(result.divergence_index)
        self.assertEqual(result.expected_trace_digest, result.actual_trace_digest)
        self.assertEqual(result.executed_steps, 3)

    def test_first_divergence_is_reported(self):
        trace = self._trace()

        def bad_executor(observation, seed, index):
            decision, action = self.deterministic_executor(observation, seed, index)
            if index == 1:
                action = dict(action)
                action["x"] += 1
            return decision, action

        result = run_replay(trace, bad_executor)
        self.assertFalse(result.matched)
        self.assertEqual(result.divergence_index, 1)
        self.assertNotEqual(result.expected_step_digest, result.actual_step_digest)

    def test_chain_digest_changes_on_reorder(self):
        trace = self._trace()
        reversed_trace = type(trace)(version=trace.version, steps=tuple(reversed(trace.steps)))
        self.assertNotEqual(trace_chain_digest(trace), trace_chain_digest(reversed_trace))


if __name__ == "__main__":
    unittest.main()
