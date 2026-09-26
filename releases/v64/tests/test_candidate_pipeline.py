import os
import sys
import tempfile
import unittest
from pathlib import Path

from fap_autonomy.candidate_pipeline import CandidatePromotionPipeline
from fap_autonomy.promotion_ledger import PromotionLedger
from fap_autonomy.verified_registry import VerifiedSkillRegistry

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "examples" / "v62_candidate"
EVAL = ROOT / "examples" / "v62_eval"


def fast_artifact(ram_mb=8.0, holdout_path=None):
    return {
        "candidate_dir": str(CAND),
        "unit_command": ["unit"],
        "dev_command": ["dev"],
        "holdout_command": ["holdout"],
        "evaluator_cwd": str(EVAL),
        "holdout_paths": [str(holdout_path or (EVAL / "holdout.jsonl"))],
        "ram_mb": ram_mb,
    }


def real_artifact(ram_mb=8.0):
    return {
        "candidate_dir": str(CAND),
        "unit_command": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        "dev_command": [sys.executable, "evaluator.py", "dev.jsonl", str(CAND)],
        "holdout_command": [sys.executable, "evaluator.py", "holdout.jsonl", str(CAND)],
        "evaluator_cwd": str(EVAL),
        "holdout_paths": [str(EVAL / "holdout.jsonl")],
        "ram_mb": ram_mb,
    }


class FakeRunner:
    def __init__(self, *, dev_score=1.0, holdout_score=1.0, tamper_path=None, invalid_dev=False):
        self.dev_score = dev_score
        self.holdout_score = holdout_score
        self.tamper_path = tamper_path
        self.invalid_dev = invalid_dev

    def run(self, command, *, cwd, extra_env=None):
        label = command[0]
        if label == "unit":
            return {"pass": True, "returncode": 0, "stdout": "ok", "stderr": "", "seconds": .01}
        if label == "dev":
            out = "not-json" if self.invalid_dev else f'{{"score":{self.dev_score},"cases":10,"passed":{round(self.dev_score*10)}}}'
            return {"pass": True, "returncode": 0, "stdout": out, "stderr": "", "seconds": .01}
        if label == "holdout":
            if self.tamper_path:
                Path(self.tamper_path).write_text("changed", encoding="utf-8")
            out = f'{{"score":{self.holdout_score},"cases":10,"passed":{round(self.holdout_score*10)}}}'
            return {"pass": True, "returncode": 0, "stdout": out, "stderr": "", "seconds": .01}
        raise AssertionError(label)


class CandidatePipelineTests(unittest.TestCase):
    def make_pipeline(self, d, registry=False, runner=None):
        reg = VerifiedSkillRegistry(os.path.join(d, "registry.json")) if registry else None
        p = CandidatePromotionPipeline(ledger=PromotionLedger(os.path.join(d, "p.sqlite3")), registry=reg)
        p.runner = runner or FakeRunner()
        return p, reg

    def test_one_success_remains_ephemeral_and_duplicate_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            p, _ = self.make_pipeline(d)
            r1 = p.evaluate_once(capability_id="MATH_GAP:percentage", artifact=fast_artifact(), trial_id="t1", baseline_dev_score=.5)
            self.assertTrue(r1["success"])
            self.assertEqual(r1["lifecycle"]["state"], "ephemeral")
            r2 = p.evaluate_once(capability_id="MATH_GAP:percentage", artifact=fast_artifact(), trial_id="t1", baseline_dev_score=.5)
            self.assertEqual(r2["status"], "duplicate_trial_or_evidence_ignored")
            self.assertEqual(r2["lifecycle"]["verified_trials"], 1)

    def test_same_evidence_new_trial_id_is_not_counted_twice(self):
        with tempfile.TemporaryDirectory() as d:
            p, _ = self.make_pipeline(d)
            a = fast_artifact()
            r1 = p.evaluate_once(capability_id="x", artifact=a, trial_id="t1", baseline_dev_score=.5)
            r2 = p.evaluate_once(capability_id="x", artifact=a, trial_id="t2", baseline_dev_score=.5)
            self.assertEqual(r1["lifecycle"]["verified_trials"], 1)
            self.assertEqual(r2["status"], "duplicate_trial_or_evidence_ignored")
            self.assertEqual(r2["lifecycle"]["verified_trials"], 1)

    def test_five_unique_verified_trials_consolidate_and_register(self):
        with tempfile.TemporaryDirectory() as d:
            p, registry = self.make_pipeline(d, registry=True)
            last = None
            for i in range(5):
                hold = Path(d) / f"holdout_{i}.jsonl"
                hold.write_text(f"shard-{i}\n", encoding="utf-8")
                last = p.evaluate_once(capability_id="MATH_GAP:percentage", artifact=fast_artifact(8.0, hold), trial_id=f"t{i}", baseline_dev_score=.5)
            self.assertEqual(last["lifecycle"]["state"], "consolidated")
            self.assertTrue(last["registered"])
            self.assertIsNotNone(registry.get("MATH_GAP:percentage"))

    def test_missing_ram_measurement_blocks_success(self):
        with tempfile.TemporaryDirectory() as d:
            p, _ = self.make_pipeline(d)
            r = p.evaluate_once(capability_id="x", artifact=fast_artifact(None), trial_id="t1", baseline_dev_score=.5)
            self.assertFalse(r["success"])
            self.assertFalse(r["evidence"]["criteria"]["resource_ok"])

    def test_static_unsafe_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            c = Path(d) / "c"
            c.mkdir()
            (c / "bad.py").write_text("exec('x=1')\n", encoding="utf-8")
            a = fast_artifact()
            a["candidate_dir"] = str(c)
            p, _ = self.make_pipeline(d)
            r = p.evaluate_once(capability_id="x", artifact=a, trial_id="t1", baseline_dev_score=.5)
            self.assertEqual(r["status"], "static_reject")

    def test_invalid_passed_greater_than_cases_rejected(self):
        class BadCountRunner(FakeRunner):
            def run(self, command, *, cwd, extra_env=None):
                if command[0] == "dev":
                    return {"pass": True, "returncode": 0, "stdout": '{"score":1.0,"cases":2,"passed":3}', "stderr": "", "seconds": .01}
                return super().run(command, cwd=cwd, extra_env=extra_env)
        with tempfile.TemporaryDirectory() as d:
            p, _ = self.make_pipeline(d, runner=BadCountRunner())
            r = p.evaluate_once(capability_id="x", artifact=fast_artifact(), trial_id="t1", baseline_dev_score=.5)
            self.assertEqual(r["status"], "dev_benchmark_invalid")

    def test_invalid_benchmark_output_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p, _ = self.make_pipeline(d, runner=FakeRunner(invalid_dev=True))
            r = p.evaluate_once(capability_id="x", artifact=fast_artifact(), trial_id="t1", baseline_dev_score=.5)
            self.assertEqual(r["status"], "dev_benchmark_invalid")

    def test_holdout_tampering_detected(self):
        with tempfile.TemporaryDirectory() as d:
            hold = Path(d) / "holdout.jsonl"
            hold.write_text("sealed\n", encoding="utf-8")
            p, _ = self.make_pipeline(d, runner=FakeRunner(tamper_path=hold))
            r = p.evaluate_once(capability_id="x", artifact=fast_artifact(8, hold), trial_id="t1", baseline_dev_score=.5)
            self.assertEqual(r["status"], "holdout_tampered")

    def test_dev_regression_blocks_success(self):
        with tempfile.TemporaryDirectory() as d:
            p, _ = self.make_pipeline(d, runner=FakeRunner(dev_score=.8, holdout_score=.8))
            r = p.evaluate_once(capability_id="x", artifact=fast_artifact(), trial_id="t1", baseline_dev_score=.9)
            self.assertFalse(r["success"])
            self.assertFalse(r["evidence"]["criteria"]["dev_ok"])

    def test_real_subprocess_fixture_one_trial(self):
        with tempfile.TemporaryDirectory() as d:
            p = CandidatePromotionPipeline(ledger=PromotionLedger(os.path.join(d, "p.sqlite3")))
            r = p.evaluate_once(capability_id="integration:demo", artifact=real_artifact(), trial_id="real-1", baseline_dev_score=.5)
            self.assertTrue(r["success"])
            self.assertEqual(r["evidence"]["holdout"]["score"], 1.0)
            self.assertEqual(r["evidence"]["resources"]["ram_source"], "measured_peak_rss")
            self.assertGreater(r["evidence"]["resources"]["ram_mb"], 0.0)


if __name__ == "__main__":
    unittest.main()
