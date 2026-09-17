import unittest
from fap_media.contracts import MediaArtifact, SkillDecision

class TestContracts(unittest.TestCase):
    def test_digest_stable(self):
        a = MediaArtifact("image", "image/png", b"abc")
        self.assertEqual(a.digest, MediaArtifact("image", "image/png", b"abc").digest)

    def test_empty_artifact_rejected(self):
        with self.assertRaises(ValueError):
            MediaArtifact("audio", "audio/wav", b"").require_nonempty()

    def test_status_closed_set(self):
        with self.assertRaises(ValueError):
            SkillDecision("maybe", "x")

if __name__ == "__main__":
    unittest.main()
