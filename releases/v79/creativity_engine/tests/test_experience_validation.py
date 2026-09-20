from __future__ import annotations

import copy
from hashlib import sha256
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_creativity import validate_experience_payload


def valid_record():
    return {
        "task_id": "task-1",
        "task_text": "省メモリ推論を改善する",
        "operator": "inversion",
        "candidate_digest": sha256(b"candidate").hexdigest(),
        "evidence_id": "evidence-1",
        "reward": 0.9,
        "verified": True,
        "stage": "ephemeral",
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
        record = valid_record()
        record["verified"] = False
        record["stage"] = "consolidated"
        with self.assertRaisesRegex(ValueError, "contradictory"):
            validate_experience_payload({"records": [record]})

    def test_verified_weak_reward_must_be_rejected(self):
        record = valid_record()
        record["reward"] = 0.2
        record["stage"] = "rejected"
        self.assertEqual(validate_experience_payload({"records": [record]})[0]["stage"], "rejected")

    def test_unknown_fields_fail_closed(self):
        record = valid_record()
        record["trusted"] = True
        with self.assertRaisesRegex(ValueError, "schema"):
            validate_experience_payload({"records": [record]})


if __name__ == "__main__":
    unittest.main()
