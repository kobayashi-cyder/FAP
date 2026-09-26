from __future__ import annotations

import argparse
import json
from pathlib import Path

from .activation_manager import ActivationManager
from .candidate_pipeline import CandidatePromotionPipeline
from .promotion_ledger import PromotionLedger
from .provenance import ProvenanceLedger
from .skill_factory_adapter import SkillFactoryOutputAdapter
from .v63_closed_loop import V63ClosedLoopCoordinator
from .verified_registry import VerifiedSkillRegistry


def main(argv=None):
    p = argparse.ArgumentParser(description="FAP V63 verified Skill Factory candidate promotion + activation")
    p.add_argument("manifest")
    p.add_argument("--candidate-root", required=True)
    p.add_argument("--evaluator-root", required=True)
    p.add_argument("--state-root", default="v63_state")
    p.add_argument("--baseline-dev-score", type=float, required=True)
    p.add_argument("--min-dev-gain", type=float, default=0.0)
    p.add_argument("--min-holdout-score", type=float, default=0.5)
    args = p.parse_args(argv)

    state = Path(args.state_root)
    state.mkdir(parents=True, exist_ok=True)
    registry = VerifiedSkillRegistry(str(state / "verified_registry.json"))
    ledger = PromotionLedger(str(state / "promotion.sqlite3"))
    provenance = ProvenanceLedger(str(state / "activation" / "provenance.jsonl"))
    activation = ActivationManager(str(state / "activation"), provenance=provenance)
    adapter = SkillFactoryOutputAdapter(candidate_root=args.candidate_root, evaluator_root=args.evaluator_root)
    pipeline = CandidatePromotionPipeline(ledger=ledger, registry=registry)
    coord = V63ClosedLoopCoordinator(adapter=adapter, pipeline=pipeline, registry=registry, activation=activation)
    result = coord.process_manifest(args.manifest, baseline_dev_score=args.baseline_dev_score,
                                    min_dev_gain=args.min_dev_gain, min_holdout_score=args.min_holdout_score)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
