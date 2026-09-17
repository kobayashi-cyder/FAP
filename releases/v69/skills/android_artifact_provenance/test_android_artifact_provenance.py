import json
import tempfile
import unittest
from pathlib import Path

from android_artifact_provenance import AndroidArtifactProvenanceWriter


class AndroidArtifactProvenanceTests(unittest.TestCase):
    def test_writes_additive_schema_three(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "state.json"
            writer = AndroidArtifactProvenanceWriter(str(out))
            data = writer.write(
                release="v69",
                source_commit="d6329968a579fa0d20dbdb115a6f7a060d13a68e",
                release_manifest_sha256="a" * 64,
                verification_sha256="b" * 64,
                active_state={"active": {"cap": {"candidate_digest": "c" * 64}}},
            )
            self.assertEqual(data["schema"], 3)
            self.assertEqual(data["release"], "v69")
            loaded = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(loaded, data)

    def test_rejects_bad_digest(self):
        with tempfile.TemporaryDirectory() as td:
            writer = AndroidArtifactProvenanceWriter(str(Path(td) / "state.json"))
            with self.assertRaises(ValueError):
                writer.write(
                    release="v69",
                    source_commit="d632996",
                    release_manifest_sha256="bad",
                    verification_sha256="b" * 64,
                    active_state={"active": {}},
                )


if __name__ == "__main__":
    unittest.main()
