import json
import tempfile
import unittest
from pathlib import Path

from artifact_binding import build_binding, binding_from_mapping, verify_binding


class ArtifactBindingTests(unittest.TestCase):
    def _build(self, td: str):
        artifact = Path(td) / "app-debug.apk"
        artifact.write_bytes(b"fake-apk-bytes-for-binding-test")
        binding = build_binding(
            artifact_path=str(artifact),
            package_name="com.example.fap",
            version_code=69,
            version_name="0.69",
            release="v69",
            source_commit="d6329968a579fa0d20dbdb115a6f7a060d13a68e",
            release_manifest_sha256="1" * 64,
            verification_sha256="2" * 64,
        )
        return artifact, binding

    def test_binding_verifies_real_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            artifact, binding = self._build(td)
            result = verify_binding(
                binding,
                artifact_path=str(artifact),
                expected_package="com.example.fap",
                expected_version_code=69,
                expected_source_commit="d6329968a579fa0d20dbdb115a6f7a060d13a68e",
            )
            self.assertTrue(result["verified"])
            self.assertEqual(result["artifact_sha256"], binding.artifact_sha256)

    def test_tampered_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            artifact, binding = self._build(td)
            artifact.write_bytes(artifact.read_bytes() + b"tamper")
            with self.assertRaises(ValueError):
                verify_binding(binding, artifact_path=str(artifact))

    def test_metadata_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            artifact, binding = self._build(td)
            with self.assertRaises(ValueError):
                verify_binding(binding, artifact_path=str(artifact), expected_package="wrong.package")
            with self.assertRaises(ValueError):
                verify_binding(binding, artifact_path=str(artifact), expected_version_code=70)

    def test_binding_round_trip_is_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            _, binding = self._build(td)
            encoded = json.dumps(binding.as_dict(), sort_keys=True)
            restored = binding_from_mapping(json.loads(encoded))
            self.assertEqual(restored, binding)
            self.assertEqual(restored.binding_sha256(), binding.binding_sha256())


if __name__ == "__main__":
    unittest.main()
