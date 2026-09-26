from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_creativity import CreativeExperienceStore, validate_experience_payload


def valid_record(
    *,
    evidence_id="evidence-1",
    stage="ephemeral",
    operator="inversion",
    reward=0.9,
    verified=True,
):
    return {
        "task_id": "task-" + evidence_id,
        "task_text": "省メモリ推論を改善する",
        "operator": operator,
        "candidate_digest": sha256(("candidate-" + evidence_id).encode()).hexdigest(),
        "evidence_id": evidence_id,
        "reward": reward,
        "verified": verified,
        "stage": stage,
    }


class ExperienceValidationTests(unittest.TestCase):
    def test_valid_record_is_accepted(self):
        records = validate_experience_payload({"records": [valid_record()]})
        self.assertEqual(records[0]["operator"], "inversion")

    def test_duplicate_persisted_evidence_fails_closed(self):
        first = valid_record()
        second = copy.deepcopy(first)
        second["task_id"] = "task-2"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_experience_payload({"records": [first, second]})

    def test_nonfinite_reward_fails_closed(self):
        record = valid_record()
        record["reward"] = float("nan")
        with self.assertRaisesRegex(ValueError, "reward"):
            validate_experience_payload({"records": [record]})

    def test_invalid_digest_fails_closed(self):
        record = valid_record()
        record["candidate_digest"] = "not-a-sha256"
        with self.assertRaisesRegex(ValueError, "digest"):
            validate_experience_payload({"records": [record]})

    def test_unverified_promoted_record_fails_closed(self):
        record = valid_record(verified=False)
        with self.assertRaisesRegex(ValueError, "promotion"):
            validate_experience_payload({"records": [record]})

    def test_verified_weak_reward_must_not_be_promoted(self):
        record = valid_record(reward=0.2)
        with self.assertRaisesRegex(ValueError, "promotion"):
            validate_experience_payload({"records": [record]})

    def test_verified_strong_reward_may_still_be_rejected(self):
        record = valid_record(stage="rejected", reward=0.95, verified=True)
        # Candidate score is not persisted, so this may be a legitimate writer
        # output for a low-score candidate and must remain representable.
        self.assertEqual(
            validate_experience_payload({"records": [record]})[0]["stage"],
            "rejected",
        )

    def test_consolidated_without_prior_successes_fails_closed(self):
        record = valid_record(stage="consolidated")
        with self.assertRaisesRegex(ValueError, "promotion history"):
            validate_experience_payload({"records": [record]})

    def test_valid_promotion_history_is_accepted(self):
        records = [
            valid_record(evidence_id="e1", stage="ephemeral"),
            valid_record(evidence_id="e2", stage="shadow"),
            valid_record(evidence_id="e3", stage="consolidated"),
            valid_record(evidence_id="e4", stage="consolidated"),
        ]
        validated = validate_experience_payload({"records": records})
        self.assertEqual(
            [x["stage"] for x in validated],
            ["ephemeral", "shadow", "consolidated", "consolidated"],
        )

    def test_promotion_history_is_per_operator(self):
        records = [
            valid_record(evidence_id="i1", stage="ephemeral", operator="inversion"),
            valid_record(evidence_id="a1", stage="ephemeral", operator="analogy"),
            valid_record(evidence_id="i2", stage="shadow", operator="inversion"),
            valid_record(evidence_id="a2", stage="shadow", operator="analogy"),
        ]
        self.assertEqual(len(validate_experience_payload({"records": records})), 4)

    def test_unknown_fields_fail_closed(self):
        record = valid_record()
        record["trusted"] = True
        with self.assertRaisesRegex(ValueError, "schema"):
            validate_experience_payload({"records": [record]})

    def test_store_load_invokes_validator(self):
        record = valid_record(stage="consolidated")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "experience.json"
            path.write_text(
                json.dumps({"records": [record]}, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "promotion history"):
                CreativeExperienceStore(path)

    def test_store_loads_valid_history(self):
        records = [
            valid_record(evidence_id="e1", stage="ephemeral"),
            valid_record(evidence_id="e2", stage="shadow"),
            valid_record(evidence_id="e3", stage="consolidated"),
        ]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "experience.json"
            path.write_text(
                json.dumps({"records": records}, ensure_ascii=False),
                encoding="utf-8",
            )
            store = CreativeExperienceStore(path)
            self.assertEqual(store.consolidated_operators(), ["inversion"])


if __name__ == "__main__":
    unittest.main()
