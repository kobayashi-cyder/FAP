from __future__ import annotations

import json
import shutil
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_teacher_learning import LearningArtifactError, TrustedTeacherLearningState


class TrustedProvenanceTests(unittest.TestCase):
    def test_reviewed_manifest_and_learning_state_load(self):
        state = TrustedTeacherLearningState()
        self.assertEqual(state.status().circuits, 10)
        self.assertEqual(state.status().memory_items, 22)

    def test_data_and_manifest_rehash_tampering_still_fails_closed(self):
        source = ROOT / "fap_teacher_learning" / "data"
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            for path in source.iterdir():
                shutil.copy2(path, target / path.name)

            data_path = target / "teacher_consolidated_circuits.json"
            circuits = json.loads(data_path.read_text(encoding="utf-8"))
            circuits["debugging"]["detect"].append("forged-cue")
            data_path.write_text(json.dumps(circuits, ensure_ascii=False), encoding="utf-8")

            canonical = json.dumps(
                circuits,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            provenance_path = target / "provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["files"]["teacher_consolidated_circuits.json"]["canonical_sha256"] = sha256(canonical).hexdigest()
            provenance_path.write_text(json.dumps(provenance, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(LearningArtifactError, "provenance digest mismatch"):
                TrustedTeacherLearningState(target)


if __name__ == "__main__":
    unittest.main()
