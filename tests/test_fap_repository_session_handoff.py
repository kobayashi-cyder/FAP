from __future__ import annotations

import json
import unittest

from fap_repository_session_handoff import RepositorySessionHandoffCodec


class RepositorySessionHandoffCodecTests(unittest.TestCase):
    def test_round_trip_preserves_content_free_identity(self) -> None:
        codec = RepositorySessionHandoffCodec()
        token = codec.encode(
            branch="horiz/coding-session-handoff",
            base_commit="a" * 40,
            plan_id="b" * 64,
            repository_digest="c" * 64,
            paths=("a.py", "tests/test_a.py"),
            sequence=3,
        )
        row = codec.decode(token)
        self.assertEqual(row.branch, "horiz/coding-session-handoff")
        self.assertEqual(row.sequence, 3)
        self.assertEqual(row.paths, ("a.py", "tests/test_a.py"))
        self.assertEqual(len(row.checksum), 64)

    def test_tampering_is_detected(self) -> None:
        codec = RepositorySessionHandoffCodec()
        token = codec.encode(
            branch="horiz/coding-session-handoff",
            base_commit="a" * 40,
            plan_id="b" * 64,
            repository_digest="c" * 64,
        )
        data = json.loads(token)
        data["sequence"] = 99
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            codec.decode(json.dumps(data))

    def test_main_branch_is_rejected(self) -> None:
        codec = RepositorySessionHandoffCodec()
        with self.assertRaisesRegex(ValueError, "non-main"):
            codec.encode(
                branch="main",
                base_commit="",
                plan_id="b" * 64,
                repository_digest="c" * 64,
            )


if __name__ == "__main__":
    unittest.main()
