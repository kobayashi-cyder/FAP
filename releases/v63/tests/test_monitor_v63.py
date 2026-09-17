import tempfile, unittest
from pathlib import Path
from fap_autonomy.post_activation_monitor import PostActivationMonitor

class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(); self.m=PostActivationMonitor(str(Path(self.td.name)/'m.db'),min_cases=4,max_success_drop=.10,max_latency_ratio=1.5)
    def tearDown(self): self.td.cleanup()
    def test_unverified_ignored(self):
        self.assertFalse(self.m.ingest(event_id='e',candidate_digest='d',verified=False,success=False,latency_ms=10))
        self.assertEqual(self.m.evaluate(candidate_digest='d',baseline_success_rate=1,baseline_latency_ms=10).verified_cases,0)
    def test_duplicate_ignored(self):
        self.assertTrue(self.m.ingest(event_id='e',candidate_digest='d',verified=True,success=True,latency_ms=10))
        self.assertFalse(self.m.ingest(event_id='e',candidate_digest='d',verified=True,success=False,latency_ms=10))
    def test_small_sample_no_rollback(self):
        for i in range(3): self.m.ingest(event_id=str(i),candidate_digest='d',verified=True,success=False,latency_ms=100)
        d=self.m.evaluate(candidate_digest='d',baseline_success_rate=1,baseline_latency_ms=10); self.assertFalse(d.rollback); self.assertEqual(d.status,'monitoring')
    def test_success_regression_rollback(self):
        for i,s in enumerate([1,0,0,0]): self.m.ingest(event_id=str(i),candidate_digest='d',verified=True,success=bool(s),latency_ms=10)
        d=self.m.evaluate(candidate_digest='d',baseline_success_rate=.95,baseline_latency_ms=10); self.assertTrue(d.rollback); self.assertIn('success_rate_regression',d.reasons)
    def test_latency_regression_rollback(self):
        for i in range(4): self.m.ingest(event_id=str(i),candidate_digest='d',verified=True,success=True,latency_ms=20)
        d=self.m.evaluate(candidate_digest='d',baseline_success_rate=1,baseline_latency_ms=10); self.assertTrue(d.rollback); self.assertIn('latency_regression',d.reasons)
    def test_healthy(self):
        for i in range(4): self.m.ingest(event_id=str(i),candidate_digest='d',verified=True,success=True,latency_ms=11)
        d=self.m.evaluate(candidate_digest='d',baseline_success_rate=.95,baseline_latency_ms=10); self.assertFalse(d.rollback); self.assertEqual(d.status,'healthy')
