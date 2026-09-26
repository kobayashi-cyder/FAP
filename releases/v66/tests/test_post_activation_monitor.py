import os
import tempfile
import unittest
from pathlib import Path

from fap_autonomy.activation_manager import ActivationManager
from fap_autonomy.post_activation_monitor import PostActivationMonitor
from fap_autonomy.promotion_ledger import digest_tree


def entry(root, cap, name):
    c = Path(root) / name; c.mkdir()
    (c / "skill.py").write_text(f"NAME={name!r}\n", encoding="utf-8")
    digest = digest_tree(str(c))
    return {"capability_id": cap, "candidate_digest": digest, "candidate_dir": str(c),
            "evidence": {"candidate_digest": digest, "lifecycle": {"state": "consolidated"},
                         "latest_evidence": {"holdout": {"score": .95}}}}


class PostActivationMonitorTests(unittest.TestCase):
    def test_unverified_and_duplicate_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            a = ActivationManager(os.path.join(d, "activation"))
            a.activate_from_registry(entry(d, "cap", "one"), baseline_quality=.9, baseline_latency_ms=100)
            m = PostActivationMonitor(os.path.join(d, "monitor.sqlite3"), a, min_samples=3)
            self.assertFalse(m.ingest(event_id="e1", capability_id="cap", verified=False, success=True, quality=.9, latency_ms=10)["accepted"])
            self.assertTrue(m.ingest(event_id="e2", capability_id="cap", verified=True, success=True, quality=.9, latency_ms=10)["accepted"])
            self.assertEqual(m.ingest(event_id="e2", capability_id="cap", verified=True, success=True, quality=.9, latency_ms=10)["reason"], "duplicate_event")

    def test_evidence_gate_prevents_single_bad_sample_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            a = ActivationManager(os.path.join(d, "activation"))
            a.activate_from_registry(entry(d, "cap", "one"), baseline_quality=.9, baseline_latency_ms=100)
            a.activate_from_registry(entry(d, "cap", "two"), baseline_quality=.9, baseline_latency_ms=100)
            m = PostActivationMonitor(os.path.join(d, "monitor.sqlite3"), a, min_samples=5)
            m.ingest(event_id="e0", capability_id="cap", verified=True, success=False, quality=.1, latency_ms=500)
            self.assertEqual(m.evaluate("cap")["status"], "insufficient_evidence")

    def test_verified_regression_rolls_back_to_previous_digest(self):
        with tempfile.TemporaryDirectory() as d:
            a = ActivationManager(os.path.join(d, "activation"))
            e1 = entry(d, "cap", "one")
            e2 = entry(d, "cap", "two")
            a.activate_from_registry(e1, baseline_quality=.9, baseline_latency_ms=100)
            a.activate_from_registry(e2, baseline_quality=.9, baseline_latency_ms=100)
            m = PostActivationMonitor(os.path.join(d, "monitor.sqlite3"), a, min_samples=5, window=5)
            for i in range(5):
                m.ingest(event_id=f"e{i}", capability_id="cap", verified=True, success=False, quality=.55, latency_ms=250)
            result = m.evaluate("cap")
            self.assertEqual(result["status"], "rollback_triggered")
            self.assertEqual(a.current("cap")["candidate_digest"], e1["candidate_digest"])

    def test_healthy_window_stays_active(self):
        with tempfile.TemporaryDirectory() as d:
            a = ActivationManager(os.path.join(d, "activation"))
            e1 = entry(d, "cap", "one")
            a.activate_from_registry(e1, baseline_quality=.9, baseline_latency_ms=100)
            m = PostActivationMonitor(os.path.join(d, "monitor.sqlite3"), a, min_samples=5, window=5)
            for i in range(5):
                m.ingest(event_id=f"e{i}", capability_id="cap", verified=True, success=True, quality=.92, latency_ms=90)
            result = m.evaluate("cap")
            self.assertEqual(result["status"], "healthy")
            self.assertEqual(a.current("cap")["candidate_digest"], e1["candidate_digest"])

    def test_invalid_metrics_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a = ActivationManager(os.path.join(d, "activation"))
            a.activate_from_registry(entry(d, "cap", "one"), baseline_quality=.9, baseline_latency_ms=100)
            m = PostActivationMonitor(os.path.join(d, "monitor.sqlite3"), a, min_samples=3)
            r = m.ingest(event_id="bad", capability_id="cap", verified=True, success=True, quality=1.2, latency_ms=-1)
            self.assertFalse(r["accepted"])
            self.assertEqual(r["reason"], "invalid_metrics")


if __name__ == "__main__":
    unittest.main()
