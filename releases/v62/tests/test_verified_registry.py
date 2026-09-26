import os
import tempfile
import unittest
from fap_autonomy.verified_registry import VerifiedSkillRegistry


class RegistryTests(unittest.TestCase):
    def test_rejects_non_consolidated(self):
        with tempfile.TemporaryDirectory() as d:
            r = VerifiedSkillRegistry(os.path.join(d, "registry.json"))
            self.assertFalse(r.register_verified("x", {}, {"candidate_digest":"d", "lifecycle":{"state":"shadow"}}))

    def test_registers_consolidated_manifest_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "registry.json")
            r = VerifiedSkillRegistry(p)
            self.assertTrue(r.register_verified("x", {"candidate_dir":"/tmp/c"}, {"candidate_digest":"d", "lifecycle":{"state":"consolidated"}}))
            entry = r.get("x")
            self.assertEqual(entry["candidate_digest"], "d")
            self.assertEqual(entry["activation"], "manual_or_existing_registry_bridge")


if __name__ == "__main__":
    unittest.main()
