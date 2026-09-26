from __future__ import annotations

import argparse
import json
from pathlib import Path

from .candidate_pipeline import CandidatePromotionPipeline
from .promotion_ledger import PromotionLedger
from .verified_registry import VerifiedSkillRegistry


def main(argv=None):
    ap = argparse.ArgumentParser(description="FAP V62 verified candidate promotion pipeline")
    ap.add_argument("artifact_json")
    ap.add_argument("--capability", required=True)
    ap.add_argument("--trial-id", required=True)
    ap.add_argument("--baseline-dev", type=float, required=True)
    ap.add_argument("--min-dev-gain", type=float, default=0.0)
    ap.add_argument("--min-holdout", type=float, default=0.5)
    ap.add_argument("--ledger", default="fap_v62_promotion.sqlite3")
    ap.add_argument("--registry", default="fap_v62_verified_registry.json")
    ap.add_argument("--out")
    ns = ap.parse_args(argv)
    artifact = json.loads(Path(ns.artifact_json).read_text(encoding="utf-8"))
    pipeline = CandidatePromotionPipeline(ledger=PromotionLedger(ns.ledger), registry=VerifiedSkillRegistry(ns.registry))
    result = pipeline.evaluate_once(capability_id=ns.capability, artifact=artifact, trial_id=ns.trial_id,
                                    baseline_dev_score=ns.baseline_dev, min_dev_gain=ns.min_dev_gain,
                                    min_holdout_score=ns.min_holdout)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if ns.out:
        Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result.get("status") in {"candidate_evaluated", "duplicate_trial_or_evidence_ignored"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
