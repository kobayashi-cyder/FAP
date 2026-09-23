from __future__ import annotations

from dataclasses import dataclass
import unittest

from fap_repository_benchmark import CodingBenchmarkCase, RepositoryCodingBenchmark


@dataclass
class Repair:
    repairs_used: int


@dataclass
class Result:
    state: str
    repair: Repair | None = None
    final_edits: tuple = ()
    errors: tuple[str, ...] = ()


class RepositoryCodingBenchmarkTests(unittest.TestCase):
    def test_summarizes_verified_rejected_and_repair_metrics(self) -> None:
        outputs = {
            "good": Result("verified_candidate", Repair(1), ("a", "b")),
            "bad": Result("rejected", Repair(2), ("a",), ("focused_command_failed:test:x",)),
        }
        report = RepositoryCodingBenchmark().run(
            (
                CodingBenchmarkCase("c1", "good"),
                CodingBenchmarkCase("c2", "bad", expected_state="rejected"),
            ),
            lambda goal: outputs[goal],
        )
        self.assertEqual(report.total_cases, 2)
        self.assertEqual(report.passed_cases, 2)
        self.assertEqual(report.pass_rate, 1.0)
        self.assertEqual(report.total_repairs, 3)
        self.assertEqual(report.total_edited_files, 3)
        self.assertEqual(
            report.results[1].error_categories,
            ("focused_command_failed:test",),
        )

    def test_executor_exception_is_categorized_without_leaking_message(self) -> None:
        def explode(goal):
            raise RuntimeError("SECRET=/private/value")

        report = RepositoryCodingBenchmark().run(
            (CodingBenchmarkCase("boom", "explode", expected_state="executor_error"),),
            explode,
        )
        row = report.results[0]
        self.assertTrue(row.passed)
        self.assertEqual(row.observed_state, "executor_error")
        self.assertEqual(row.error_categories, ("executor_error:RuntimeError",))
        self.assertNotIn("SECRET", repr(row.to_dict()))

    def test_duplicate_case_id_is_rejected(self) -> None:
        cases = (
            CodingBenchmarkCase("same", "one"),
            CodingBenchmarkCase("same", "two"),
        )
        with self.assertRaisesRegex(ValueError, "duplicate benchmark"):
            RepositoryCodingBenchmark().run(cases, lambda goal: Result("verified_candidate"))


if __name__ == "__main__":
    unittest.main()
