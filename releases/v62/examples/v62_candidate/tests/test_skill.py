import unittest
from skill import solve


class SkillTests(unittest.TestCase):
    def test_percent(self):
        self.assertEqual(solve("percent 20 250"), "50")

    def test_ratio(self):
        self.assertEqual(solve("ratio 12 3"), "4")

    def test_unknown(self):
        self.assertEqual(solve("hello"), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
