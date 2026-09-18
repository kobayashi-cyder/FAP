from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_autonomy.candidate_pipeline import CandidatePromotionPipeline
from fap_autonomy.promotion_ledger import PromotionLedger
from fap_autonomy.verified_registry import VerifiedSkillRegistry

CAND = ROOT / "examples" / "v62_candidate"
EVAL = ROOT / "examples" / "v62_eval"
REPORT = ROOT / "reports" / "demo_v62_closed_loop.json"
LEDGER = ROOT / "reports" / "demo_v62_promotion.sqlite3"
REGISTRY = ROOT / "reports" / "demo_v62_registry.json"

for p in (LEDGER, REGISTRY):
    if p.exists():
        p.unlink()

pipeline = CandidatePromotionPipeline(
    ledger=PromotionLedger(str(LEDGER)),
    registry=VerifiedSkillRegistry(str(REGISTRY)),
)
rows = []
for i in range(1, 6):
    holdout = EVAL / f"holdout_{i}.jsonl"
    artifact = {
        "candidate_dir": str(CAND),
        "unit_command": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        "dev_command": [sys.executable, "evaluator.py", "dev.jsonl", str(CAND)],
        "holdout_command": [sys.executable, "evaluator.py", holdout.name, str(CAND)],
        "evaluator_cwd": str(EVAL),
        "holdout_paths": [str(holdout)],
    }
    r = pipeline.evaluate_once(
        capability_id="MATH_GAP:demo_percentage_ratio",
        artifact=artifact,
        trial_id=f"v62-demo-shard-{i}",
        baseline_dev_score=0.50,
        min_dev_gain=0.10,
        min_holdout_score=0.75,
    )
    rows.append({
        "trial_id": r["trial_id"],
        "status": r["status"],
        "success": r.get("success"),
        "state": r.get("lifecycle", {}).get("state"),
        "verified_trials": r.get("lifecycle", {}).get("verified_trials"),
        "dev_score": r.get("evidence", {}).get("dev", {}).get("score"),
        "holdout_score": r.get("evidence", {}).get("holdout", {}).get("score"),
        "peak_rss_mb": r.get("evidence", {}).get("resources", {}).get("ram_mb"),
        "ram_source": r.get("evidence", {}).get("resources", {}).get("ram_source"),
        "evidence_key": r.get("evidence", {}).get("evidence_key"),
        "registered": r.get("registered"),
    })
REPORT.write_text(json.dumps({"synthetic_demo": True, "trials": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(REPORT.read_text(encoding="utf-8"))
