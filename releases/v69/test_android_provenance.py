import json
import tempfile
import unittest
from pathlib import Path

from android_provenance import PackageMetadata, build_provenance, from_mapping, verify_provenance

SHA = "9" * 40
META = PackageMetadata("com.example.fap", 69, "69.0")


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.artifact = Path(self.tmp.name) / "app.apk"
        self.artifact.write_bytes((b"FAP-V69-fixture\0" * 4096))
        self.manifest = b'{"release":"v69"}'
        self.summary = b'{"tests":"synthetic"}'

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        return build_provenance(self.artifact, META, SHA, "v69", self.manifest, self.summary)

    def test_deterministic_round_trip(self):
        a, b = self.build(), self.build()
        self.assertEqual(a.canonical_bytes(), b.canonical_bytes())
        obj = json.loads(a.canonical_bytes())
        self.assertEqual(from_mapping(obj), a)
        self.assertTrue(verify_provenance(a, self.artifact, META, SHA, self.manifest, self.summary))

    def test_one_byte_mutation_fails_closed(self):
        record = self.build()
        data = bytearray(self.artifact.read_bytes()); data[-1] ^= 1; self.artifact.write_bytes(data)
        with self.assertRaises(ValueError): verify_provenance(record, self.artifact)

    def test_missing_and_truncated_artifact_fail(self):
        record = self.build()
        self.artifact.write_bytes(b"short")
        with self.assertRaises(ValueError): verify_provenance(record, self.artifact)
        self.artifact.unlink()
        with self.assertRaises(FileNotFoundError): verify_provenance(record, self.artifact)

    def test_package_version_and_source_mismatch_fail(self):
        record = self.build()
        for meta in [PackageMetadata("wrong.pkg",69,"69.0"), PackageMetadata(META.package_name,70,"69.0"), PackageMetadata(META.package_name,69,"wrong")]:
            with self.assertRaises(ValueError): verify_provenance(record, self.artifact, meta)
        with self.assertRaises(ValueError): verify_provenance(record, self.artifact, expected_source_sha="8" * 40)
        with self.assertRaises(ValueError): build_provenance(self.artifact, META, "bad", "v69")

    def test_manifest_and_summary_mismatch_fail(self):
        record = self.build()
        with self.assertRaises(ValueError): verify_provenance(record, self.artifact, release_manifest=b"bad", verification_summary=self.summary)
        with self.assertRaises(ValueError): verify_provenance(record, self.artifact, release_manifest=self.manifest, verification_summary=b"bad")

    def test_optional_evidence_is_explicit(self):
        record = build_provenance(self.artifact, META, SHA, "v69")
        self.assertTrue(verify_provenance(record, self.artifact))
        with self.assertRaises(ValueError): verify_provenance(record, self.artifact, release_manifest=b"unexpected")

    def test_malformed_mapping_rejected(self):
        obj = json.loads(self.build().canonical_bytes())
        for key, value in [("artifact_sha256", "bad"), ("source_sha", "bad")]:
            bad = dict(obj); bad[key] = value
            with self.assertRaises(ValueError): from_mapping(bad)
        extra = dict(obj); extra["secret"] = "x"
        with self.assertRaises(ValueError): from_mapping(extra)

    def test_serialized_record_has_no_private_payload(self):
        text = self.build().canonical_bytes().decode()
        for forbidden in ["microphone", "audio", "token", "device_id", self.tmp.name]:
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
