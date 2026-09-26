from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_version_consistency",
    ROOT / "scripts" / "check_version_consistency.py",
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PublicReleaseContractTests(unittest.TestCase):
    def test_current_tree_is_consistent(self):
        version, base, revision = module.validate(ROOT)
        self.assertEqual(version, "1.0.01")
        self.assertEqual(base, "1.0.01")
        self.assertIsNone(revision)

    def test_reset_revision_format_is_supported(self):
        self.assertEqual(module.parse_version("1.0.0-r001"), ("1.0.0", "r001"))

    def test_three_component_candidate_is_supported(self):
        self.assertEqual(module.parse_version("1.0.01"), ("1.0.01", None))

    def test_legacy_two_component_version_is_rejected(self):
        with self.assertRaises(SystemExit):
            module.parse_version("87.81")


if __name__ == "__main__":
    unittest.main()
