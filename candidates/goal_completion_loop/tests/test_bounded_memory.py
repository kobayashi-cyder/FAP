from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_goal_loop.bounded_memory import BoundedHotColdMemory


class BoundedHotColdMemoryTests(unittest.TestCase):
    def test_memory_is_strictly_bounded(self):
        memory = BoundedHotColdMemory(hot_capacity=2, cold_capacity=3, page_in=2)
        for i in range(10):
            memory.remember(str(i), f"topic {i}", utility=i / 10)
        self.assertLessEqual(memory.size, 5)
        self.assertLessEqual(len(memory.hot), 2)
        self.assertLessEqual(len(memory.cold), 3)

    def test_retrieval_pages_relevant_item_into_hot(self):
        memory = BoundedHotColdMemory(hot_capacity=1, cold_capacity=4, page_in=1)
        memory.remember("fly", "mushroom body kenyon cells", utility=0.5)
        memory.remember("weather", "rain pressure cloud", utility=0.0)
        got = memory.retrieve("mushroom kenyon")
        self.assertEqual(got[0].key, "fly")
        self.assertIn("fly", memory.hot)
        self.assertEqual(got[0].accesses, 1)

    def test_high_confidence_and_contradictions_survive_first(self):
        memory = BoundedHotColdMemory(hot_capacity=1, cold_capacity=2, page_in=1)
        memory.remember("certain", "verified fact", confidence=0.95)
        memory.remember("conflict", "contradictory fact", contradiction_group="g")
        memory.remember("weak1", "weak fact one", confidence=0.1)
        memory.remember("weak2", "weak fact two", confidence=0.1)
        keys = set(memory.hot) | set(memory.cold)
        self.assertIn("certain", keys)
        self.assertIn("conflict", keys)

    def test_empty_query_does_not_page_arbitrary_memory(self):
        memory = BoundedHotColdMemory(hot_capacity=1, cold_capacity=2, page_in=1)
        memory.remember("a", "some memory")
        self.assertEqual(memory.retrieve("   "), ())


if __name__ == "__main__":
    unittest.main()
