import os
import tempfile
import unittest
from pathlib import Path

from fap_autonomy.activation_manager import ActivationManager
from fap_autonomy.promotion_ledger import digest_tree


def make_entry(root, cap, text, state="consolidated"):
    c = Path(root) / ("candidate_" + text.replace(" ", "_"))
    c.mkdir()
    (c / "skill.py").write_text(f"VALUE = {text!r}\n", encoding="utf-8")
    digest = digest_tree(str(c))
    return {
        "capability_id": cap,
        "candidate_digest": digest,
        "candidate_dir": str(c),
        "evidence": {
            "candidate_digest": digest,
            "lifecycle": {"state": state},
            "latest_evidence": {"holdout": {"score": 0.95}},
        },
    }


class ActivationManagerTests(unittest.TestCase):
    def test_rejects_non_consolidated(self):
        with tempfile.TemporaryDirectory() as d:
            m = ActivationManager(os.path.join(d, "active"))
            e = make_entry(d, "cap", "one", state="shadow")
            with self.assertRaises(ValueError):
                m.stage_from_registry(e)

    def test_digest_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            m = ActivationManager(os.path.join(d, "active"))
            e = make_entry(d, "cap", "one")
            e["candidate_digest"] = "0" * 64
            with self.assertRaises(ValueError):
                m.stage_from_registry(e)

    def test_activate_snapshot_and_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            m = ActivationManager(os.path.join(d, "active"))
            e1 = make_entry(d, "cap", "one")
            e2 = make_entry(d, "cap", "two")
            r1 = m.activate_from_registry(e1, baseline_quality=.9, baseline_latency_ms=100)
            self.assertTrue(r1["activated"])
            self.assertTrue(Path(r1["entry"]["slot"]).is_dir())
            r2 = m.activate_from_registry(e2, baseline_quality=.92, baseline_latency_ms=90)
            self.assertTrue(r2["activated"])
            self.assertEqual(m.current("cap")["candidate_digest"], e2["candidate_digest"])
            rb = m.rollback("cap", reason="regression")
            self.assertTrue(rb["rolled_back"])
            self.assertEqual(m.current("cap")["candidate_digest"], e1["candidate_digest"])
            self.assertTrue(m.provenance.verify()["valid"])

    def test_same_digest_does_not_reactivate(self):
        with tempfile.TemporaryDirectory() as d:
            m = ActivationManager(os.path.join(d, "active"))
            e = make_entry(d, "cap", "same")
            self.assertTrue(m.activate_from_registry(e)["activated"])
            r = m.activate_from_registry(e)
            self.assertFalse(r["activated"])
            self.assertEqual(r["reason"], "already_active")

    def test_symlink_candidate_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unsupported")
        with tempfile.TemporaryDirectory() as d:
            m = ActivationManager(os.path.join(d, "active"))
            e = make_entry(d, "cap", "one")
            outside = Path(d) / "outside.txt"; outside.write_text("secret", encoding="utf-8")
            link = Path(e["candidate_dir"]) / "link.txt"
            try:
                os.symlink(outside, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            e["candidate_digest"] = digest_tree(e["candidate_dir"])
            e["evidence"]["candidate_digest"] = e["candidate_digest"]
            with self.assertRaises(ValueError):
                m.stage_from_registry(e)

    def test_rollback_refuses_tampered_previous_slot(self):
        with tempfile.TemporaryDirectory() as d:
            m = ActivationManager(os.path.join(d, "active"))
            e1 = make_entry(d, "cap", "one")
            e2 = make_entry(d, "cap", "two")
            m.activate_from_registry(e1)
            m.activate_from_registry(e2)
            state = m._load()
            previous_slot = Path(state["history"]["cap"][-1]["slot"])
            (previous_slot / "skill.py").write_text("TAMPERED=True\n", encoding="utf-8")
            rb = m.rollback("cap", reason="regression")
            self.assertFalse(rb["rolled_back"])
            self.assertEqual(rb["reason"], "previous_slot_integrity_failed")
            self.assertEqual(m.current("cap")["candidate_digest"], e2["candidate_digest"])


if __name__ == "__main__":
    unittest.main()
