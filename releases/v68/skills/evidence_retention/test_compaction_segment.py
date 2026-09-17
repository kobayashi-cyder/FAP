import tempfile
import unittest
from pathlib import Path

from compaction_segment import (
    CompactionRecord,
    atomic_write_segment,
    build_segment,
    verify_segment,
)


class CompactionSegmentTests(unittest.TestCase):
    def _records(self):
        return [
            CompactionRecord("e2", "cap-b", 2.0, {"result": "ok", "latency": 12}),
            CompactionRecord("e1", "cap-a", 1.0, {"result": "ok", "latency": 10}),
            CompactionRecord("e3", "cap-a", 3.0, {"result": "fail", "reason": "x"}),
        ]

    def test_segment_is_deterministic_independent_of_input_order(self):
        a_blob, a_manifest = build_segment(self._records())
        b_blob, b_manifest = build_segment(reversed(self._records()))
        self.assertEqual(a_blob, b_blob)
        self.assertEqual(a_manifest, b_manifest)
        self.assertEqual(a_manifest.evidence_ids, ("e1", "e3", "e2"))

    def test_round_trip_verifies_exact_contents(self):
        blob, manifest = build_segment(self._records())
        rows = verify_segment(blob, manifest)
        self.assertEqual(len(rows), 3)
        self.assertEqual(tuple(r["evidence_id"] for r in rows), manifest.evidence_ids)
        self.assertLess(manifest.compressed_bytes, manifest.raw_bytes + 128)

    def test_tamper_is_rejected(self):
        blob, manifest = build_segment(self._records())
        tampered = bytearray(blob)
        tampered[-1] ^= 1
        with self.assertRaises(ValueError):
            verify_segment(bytes(tampered), manifest)

    def test_duplicate_evidence_id_is_rejected(self):
        records = [
            CompactionRecord("same", "cap-a", 1.0, {}),
            CompactionRecord("same", "cap-b", 2.0, {}),
        ]
        with self.assertRaises(ValueError):
            build_segment(records)

    def test_atomic_write_only_accepts_verified_blob(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "segment.jsonl.gz"
            blob, manifest = build_segment(self._records())
            atomic_write_segment(str(target), blob, manifest)
            self.assertEqual(target.read_bytes(), blob)
            with self.assertRaises(ValueError):
                atomic_write_segment(str(target), blob + b"bad", manifest)
            self.assertEqual(target.read_bytes(), blob)


if __name__ == "__main__":
    unittest.main()
