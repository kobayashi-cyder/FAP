from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_goal_loop import ExchangeCapsule


class ExchangeFilesTests(unittest.TestCase):
    def test_all_exchange_capsules_parse(self):
        root = ROOT / "exchange"
        files = sorted(root.glob("*.json"))
        self.assertTrue(files)
        for path in files:
            cap = ExchangeCapsule.from_json(path.read_text(encoding="utf-8"))
            self.assertEqual(len(cap.digest), 64)
            self.assertIn(cap.source_project, {"FAP", "FCA"})


if __name__ == "__main__":
    unittest.main()
