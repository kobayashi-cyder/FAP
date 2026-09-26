import unittest
from fap_autonomy import BenchmarkCase, BenchmarkResult, FailureClusterAnalyzer, GapType


class FailureAnalyzerTests(unittest.TestCase):
    def test_hierarchical_math_failure(self):
        r = BenchmarkResult(
            BenchmarkCase("m1", "math", "word problem multi-step quantity relation"),
            success=False, error="wrong answer", teacher_used=True, latency_ms=12,
        )
        e = FailureClusterAnalyzer().classify(r)
        self.assertEqual(e.gap, GapType.MATH_GAP)
        self.assertEqual(e.hierarchy, ("word_problem", "quantity_relation", "multi_step"))

    def test_code_compile_failure(self):
        r = BenchmarkResult(BenchmarkCase("c1", "code", "repository patch"), False, error="compile failed")
        e = FailureClusterAnalyzer().classify(r)
        self.assertEqual(e.gap, GapType.CODE_GAP)
        self.assertEqual(e.hierarchy[-1], "compile_repair")

    def test_clusters_count_and_teacher_dependency(self):
        case = BenchmarkCase("m1", "math", "word problem multi-step quantity relation")
        rows = [
            BenchmarkResult(case, False, teacher_used=True),
            BenchmarkResult(BenchmarkCase("m2", "math", case.task), True, teacher_used=True),
        ]
        c = FailureClusterAnalyzer().cluster(rows)[0]
        self.assertEqual(c.count, 1)
        self.assertEqual(c.total_in_family, 2)
        self.assertAlmostEqual(c.success_rate, 0.5)
        self.assertAlmostEqual(c.teacher_dependency, 1.0)


if __name__ == "__main__":
    unittest.main()
