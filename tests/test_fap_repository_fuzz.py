from __future__ import annotations

import unittest

from fap_repository_fuzz import (
    FuzzLexicon,
    RepositoryCodingFuzzer,
    classify_failure,
)


class RepositoryCodingFuzzerTests(unittest.TestCase):
    def lexicon(self) -> FuzzLexicon:
        return FuzzLexicon(
            verbs=("update", "fix", "create", "delete"),
            targets=("a.py", "b.py", "notes.md"),
            qualifiers=("and run tests", "without changing API", "minimize diff"),
            conjunctions=(" and ", " then ", " / "),
        )

    def test_same_seed_is_reproducible(self) -> None:
        fuzzer = RepositoryCodingFuzzer(self.lexicon())
        a = fuzzer.generate(seed=42, count=25)
        b = fuzzer.generate(seed=42, count=25)
        self.assertEqual(a, b)
        self.assertEqual(len({row.goal for row in a}), 25)

    def test_different_seed_changes_corpus(self) -> None:
        fuzzer = RepositoryCodingFuzzer(self.lexicon())
        a = fuzzer.generate(seed=1, count=10)
        b = fuzzer.generate(seed=2, count=10)
        self.assertNotEqual(
            tuple(row.goal for row in a),
            tuple(row.goal for row in b),
        )

    def test_failure_classifier_drops_arbitrary_tail(self) -> None:
        categories = classify_failure(
            (
                "proposal_provider_failed:RuntimeError:SECRET=/private/path",
                "focused_command_failed:test_calc:huge output",
            )
        )
        self.assertEqual(
            categories,
            (
                "proposal_provider_failed:RuntimeError",
                "focused_command_failed:test_calc",
            ),
        )
        self.assertNotIn("SECRET", repr(categories))

    def test_failure_classifier_redacts_two_field_and_unstructured_messages(self) -> None:
        categories = classify_failure(
            (
                "ValueError: SECRET=/private/path",
                "SECRET=/private/path",
                "proposal_provider_failed:SECRET=/private/path",
                "proposal_provider_failed:RuntimeError:SECRET=/private/path",
            )
        )
        self.assertEqual(
            categories,
            (
                "exception:ValueError",
                "unclassified_failure",
                "proposal_provider_failed",
                "proposal_provider_failed:RuntimeError",
            ),
        )
        self.assertNotIn("SECRET", repr(categories))
        self.assertNotIn("/private/path", repr(categories))

    def test_empty_conjunctions_fail_closed_for_multiple_clauses(self) -> None:
        fuzzer = RepositoryCodingFuzzer(
            FuzzLexicon(
                verbs=("fix",),
                targets=("a.py", "b.py"),
                conjunctions=(),
            )
        )
        with self.assertRaisesRegex(ValueError, "conjunctions must be non-empty"):
            fuzzer.generate(seed=0, count=1, max_clauses=2)

        rows = fuzzer.generate(seed=0, count=2, max_clauses=1)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(" and " not in row.goal for row in rows))

    def test_small_lexicon_fails_when_unique_space_exhausted(self) -> None:
        fuzzer = RepositoryCodingFuzzer(
            FuzzLexicon(verbs=("fix",), targets=("a.py",), conjunctions=(" and ",))
        )
        with self.assertRaisesRegex(ValueError, "unique cases"):
            fuzzer.generate(seed=0, count=3, max_clauses=1)


if __name__ == "__main__":
    unittest.main()
