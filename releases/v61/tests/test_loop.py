import unittest
from fap_autonomy import AutonomousCapabilityLoop, BenchmarkCase, BenchmarkResult


class Runner:
    def run(self, split):
        if split == "dev":
            return [
                BenchmarkResult(BenchmarkCase("m1", "math", "word problem multi-step quantity relation"), False, teacher_used=True),
                BenchmarkResult(BenchmarkCase("m2", "math", "word problem multi-step quantity relation"), True, teacher_used=True),
                BenchmarkResult(BenchmarkCase("c1", "code", "repository compile repair"), False),
            ]
        return [BenchmarkResult(BenchmarkCase("h1", "math", "word problem multi-step quantity relation"), True, verified=True)]


class LoopTests(unittest.TestCase):
    def test_diagnose_selects_real_cluster(self):
        report = AutonomousCapabilityLoop(Runner()).diagnose()
        self.assertEqual(report["dev"]["cases"], 3)
        self.assertGreaterEqual(len(report["clusters"]), 2)
        self.assertIsNotNone(report["selected"])

    def test_without_factory_stops_before_code_execution(self):
        report = AutonomousCapabilityLoop(Runner()).cycle_once()
        self.assertEqual(report["status"], "candidate_selected_bridge_required")


if __name__ == "__main__":
    unittest.main()
