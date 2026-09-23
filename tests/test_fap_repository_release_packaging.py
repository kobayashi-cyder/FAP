from __future__ import annotations

import unittest

from fap_repository_release_packaging import (
    IntegrationWorkstream,
    RepositoryIntegrationManifestBuilder,
)


class RepositoryIntegrationManifestBuilderTests(unittest.TestCase):
    def row(self, branch: str, sha: str, pr: int, ci: str = "success"):
        return IntegrationWorkstream(
            branch=branch,
            head_sha=sha,
            pr_number=pr,
            ci_conclusion=ci,
            changed_files=("b.py", "a.py", "a.py"),
        )

    def test_manifest_is_order_independent_and_canonical(self) -> None:
        builder = RepositoryIntegrationManifestBuilder()
        a = self.row("horiz/coding-python", "a" * 40, 128)
        b = self.row("horiz/coding-security", "b" * 40, 131)
        left = builder.build(
            release_line="87.81",
            base_sha="c" * 40,
            workstreams=(a, b),
        )
        right = builder.build(
            release_line="87.81",
            base_sha="c" * 40,
            workstreams=(b, a),
        )
        self.assertEqual(left.digest, right.digest)
        self.assertEqual(
            tuple(x.branch for x in left.workstreams),
            ("horiz/coding-python", "horiz/coding-security"),
        )
        self.assertEqual(left.workstreams[0].changed_files, ("a.py", "b.py"))

    def test_non_green_workstream_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "CI is not green"):
            RepositoryIntegrationManifestBuilder().build(
                release_line="87.81",
                base_sha="c" * 40,
                workstreams=(
                    self.row("horiz/coding-python", "a" * 40, 128, "failure"),
                ),
            )

    def test_direct_main_style_branch_is_not_accepted(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid horizontal branch"):
            RepositoryIntegrationManifestBuilder().build(
                release_line="87.81",
                base_sha="c" * 40,
                workstreams=(
                    self.row("main", "a" * 40, 1),
                ),
            )


if __name__ == "__main__":
    unittest.main()
