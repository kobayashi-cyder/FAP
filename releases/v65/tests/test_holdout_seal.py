import os
import tempfile
import unittest
from pathlib import Path
from fap_autonomy.holdout_seal import HoldoutSeal


class HoldoutSealTests(unittest.TestCase):
    def test_intact(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.jsonl")
            Path(p).write_text("x\n", encoding="utf-8")
            s = HoldoutSeal([p])
            self.assertTrue(s.verify()["intact"])

    def test_detects_change(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.jsonl")
            Path(p).write_text("x\n", encoding="utf-8")
            s = HoldoutSeal([p])
            with open(p, "a", encoding="utf-8") as f:
                f.write("y\n")
            self.assertFalse(s.verify()["intact"])


if __name__ == "__main__":
    unittest.main()
