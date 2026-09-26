from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from fap_semantic_memory import SemanticMemoryStore


class SemanticMemoryStoreTests(unittest.TestCase):
    def test_recall_question_does_not_overwrite_fact_slot(self):
        with TemporaryDirectory() as root:
            store = SemanticMemoryStore(root)
            store.absorb_user("s", "合言葉はK123456789")
            before = store.retrieve("s", "合言葉", limit=4)
            self.assertTrue(any("K123456789" in row.get("text", "") for row in before))

            store.absorb_user("s", "合言葉を覚えている？")
            after = store.retrieve("s", "合言葉を覚えている？", limit=4)

            self.assertTrue(any("K123456789" in row.get("text", "") for row in after))
            self.assertFalse(any(row.get("text") == "合言葉を覚えている" for row in after))


if __name__ == "__main__":
    unittest.main()
