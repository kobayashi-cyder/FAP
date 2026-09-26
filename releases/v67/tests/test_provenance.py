import json
import os
import tempfile
import unittest
from pathlib import Path

from fap_autonomy.provenance import ProvenanceLedger


class ProvenanceTests(unittest.TestCase):
    def test_hash_chain_verifies_and_detects_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p.jsonl")
            ledger = ProvenanceLedger(p)
            ledger.append("one", capability_id="x", candidate_digest="a" * 64, payload={"v": 1})
            ledger.append("two", capability_id="x", candidate_digest="b" * 64, payload={"v": 2})
            self.assertTrue(ledger.verify()["valid"])
            with open(p, encoding="utf-8") as src:
                rows = [json.loads(x) for x in src if x.strip()]
            rows[0]["payload"]["v"] = 999
            with open(p, "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, sort_keys=True) + "\n")
            self.assertFalse(ledger.verify()["valid"])

    def test_empty_ledger_is_valid(self):
        with tempfile.TemporaryDirectory() as d:
            result = ProvenanceLedger(os.path.join(d, "p.jsonl")).verify()
            self.assertTrue(result["valid"])
            self.assertEqual(result["entries"], 0)

    def test_append_refuses_tampered_chain(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p.jsonl")
            ledger = ProvenanceLedger(p)
            ledger.append("one", payload={"x": 1})
            text = Path(p).read_text(encoding="utf-8").replace('"x": 1', '"x": 2')
            Path(p).write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                ledger.append("two")


if __name__ == "__main__":
    unittest.main()
