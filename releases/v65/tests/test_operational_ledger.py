import tempfile
import unittest
from pathlib import Path
from fap_autonomy.operational_ledger import OperationalLedger


class OperationalLedgerTests(unittest.TestCase):
    def test_unverified_excluded_and_duplicates_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = OperationalLedger(str(Path(td) / "s.db"), audit_fraction=0.0)
            rows = [
                {"turn_id": "a", "text": "x", "intent": "math", "domain": "math", "verified": False},
                {"turn_id": "b", "text": "word problem percentage", "intent": "math", "domain": "math", "feedback": "bad"},
            ]
            r1 = ledger.ingest_rows(rows)
            r2 = ledger.ingest_rows(rows)
            self.assertEqual(r1["inserted"], 1)
            self.assertEqual(r2["duplicates"], 1)
            self.assertEqual(ledger.counts()["all"], 1)

    def test_audit_bucket_is_separate(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = OperationalLedger(str(Path(td) / "s.db"), audit_fraction=1.0 - 1e-12)
            rows = [{"turn_id": f"t{i}", "text": "x", "intent": "reasoning", "domain": "reasoning", "feedback": "bad"} for i in range(50)]
            ledger.ingest_rows(rows)
            self.assertGreater(ledger.counts()["audit"], 0)
            self.assertEqual(len(ledger.results("diagnostic")) + len(ledger.results("audit")), ledger.counts()["all"])
