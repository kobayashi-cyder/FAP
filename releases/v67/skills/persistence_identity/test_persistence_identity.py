import tempfile
import unittest
from pathlib import Path

from persistence_identity import ScopedEvidenceLedger, scoped_identity


class PersistenceIdentityTests(unittest.TestCase):
    def test_scoped_identity_changes_across_capabilities(self):
        a = scoped_identity("cap-a", "event-1")
        b = scoped_identity("cap-b", "event-1")
        self.assertNotEqual(a, b)
        self.assertEqual(a, scoped_identity("cap-a", "event-1"))

    def test_cross_capability_event_ids_do_not_collide(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "ledger.sqlite3")
            ledger = ScopedEvidenceLedger(path)
            self.assertTrue(ledger.insert(capability_id="cap-a", event_id="event-1", candidate_digest="d1", attestation_id="att-1", payload={"ok": True}))
            self.assertTrue(ledger.insert(capability_id="cap-b", event_id="event-1", candidate_digest="d2", attestation_id="att-2", payload={"ok": True}))
            self.assertFalse(ledger.insert(capability_id="cap-a", event_id="event-1", candidate_digest="d3", attestation_id="att-3", payload={"ok": False}))
            self.assertEqual(ledger.counts(), {"cap-a": 1, "cap-b": 1})

    def test_attestation_remains_globally_single_use(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "ledger.sqlite3")
            ledger = ScopedEvidenceLedger(path)
            self.assertTrue(ledger.insert(capability_id="cap-a", event_id="e1", candidate_digest="d1", attestation_id="att-1", payload={}))
            self.assertFalse(ledger.insert(capability_id="cap-b", event_id="e2", candidate_digest="d2", attestation_id="att-1", payload={}))

    def test_restart_preserves_schema_and_rows(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "ledger.sqlite3")
            first = ScopedEvidenceLedger(path)
            self.assertTrue(first.insert(capability_id="cap", event_id="e", candidate_digest="d", attestation_id="a", payload={}))
            second = ScopedEvidenceLedger(path)
            self.assertEqual(second.counts(), {"cap": 1})


if __name__ == "__main__":
    unittest.main()
