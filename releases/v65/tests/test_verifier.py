import tempfile
import unittest
from pathlib import Path
from fap_autonomy.verifier import StaticSafetyGate, SafeCandidateVerifier


class VerifierTests(unittest.TestCase):
    def test_rejects_exec(self):
        r = StaticSafetyGate().inspect_source("exec('print(1)')")
        self.assertFalse(r["safe"])

    def test_rejects_network_import(self):
        r = StaticSafetyGate().inspect_source("import socket\n")
        self.assertFalse(r["safe"])

    def test_benign_candidate_executes_tests(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            (root / "candidate.py").write_text("def add(a,b): return a+b\n", encoding="utf-8")
            (root / "tests" / "test_candidate.py").write_text(
                "import unittest\nfrom candidate import add\n"
                "class T(unittest.TestCase):\n    def test_add(self): self.assertEqual(add(2,3),5)\n",
                encoding="utf-8",
            )
            r = SafeCandidateVerifier(timeout_seconds=5).verify(
                {"candidate_dir": d, "ram_mb": 4.0}, capability_id="demo"
            )
            self.assertTrue(r["static_safe"])
            self.assertTrue(r["unit_pass"])
            self.assertTrue(r["sandbox_pass"])
            self.assertTrue(r["resource_measurement_complete"])

    def test_missing_ram_is_explicitly_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            (root / "candidate.py").write_text("x=1\n", encoding="utf-8")
            (root / "tests" / "test_candidate.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n    def test_x(self): self.assertTrue(True)\n",
                encoding="utf-8",
            )
            r = SafeCandidateVerifier(timeout_seconds=5).verify({"candidate_dir": d}, capability_id="demo")
            self.assertTrue(r["unit_pass"])
            self.assertFalse(r["resource_measurement_complete"])
            self.assertIsNone(r["resources"]["ram_mb"])


if __name__ == "__main__":
    unittest.main()
