from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from collections import Counter
from pathlib import Path

from fap_literature_review import CrossrefHarvester, CriticalAppraiser


KIND_WEIGHT = {
    "contradiction": 1.00,
    "causality": 0.98,
    "validation": 0.97,
    "robustness": 0.96,
    "future_test": 0.95,
    "open_question": 0.95,
    "generalization": 0.92,
    "uncertainty": 0.90,
    "scale": 0.88,
    "confounding": 0.88,
    "bias": 0.86,
    "mechanism": 0.84,
    "prospective_prediction": 0.84,
    "replication": 0.82,
}


def _question_kind(row: dict) -> str:
    questions = row.get("research_questions") or []
    if questions:
        return str(questions[0].get("kind", "open_question"))
    unresolved = row.get("top_unresolved_kinds") or []
    if unresolved:
        first = unresolved[0]
        if isinstance(first, (list, tuple)) and first:
            return str(first[0])
    return "open_question"


def _question_text(row: dict) -> str:
    questions = row.get("research_questions") or []
    if questions:
        return str(questions[0].get("question", "")).strip()
    return f"{row.get('topic','この分野')}で最も重要な未解決問題は何か？"


def _source_dois(row: dict, limit: int = 12) -> list[str]:
    out = []
    for paper in row.get("example_papers") or []:
        doi = str(paper.get("doi", "")).strip().lower()
        if doi and doi not in out:
            out.append(doi)
        if len(out) >= limit:
            break
    return out


def _base_hypotheses(row: dict) -> list[dict]:
    topic = str(row.get("topic", "対象"))
    loops = row.get("provisional_hypothesis_falsification_loops") or []
    out = []

    if loops:
        first = loops[0]
        out.append({
            "kind": "frontier-derived",
            "statement": str(first.get("hypothesis", "")).strip(),
            "falsifier": str(first.get("falsifier", "")).strip(),
            "next_test": str(first.get("next_test", "")).strip(),
        })

    out.append({
        "kind": "method-artifact",
        "statement": f"{topic}で報告される差や不一致の一部は、測定法・対象選択・解析仕様の違いで生じている可能性がある。",
        "falsifier": "測定法・対象・解析仕様をそろえた独立データでも同じ差が再現する。",
        "next_test": "条件を層別化した独立再解析と外部検証を行う。",
    })
    out.append({
        "kind": "regime-dependence",
        "statement": f"{topic}の主要効果または支配機構は、環境・集団・時間空間スケールによって切り替わる可能性がある。",
        "falsifier": "広い条件範囲で単一モデル・単一効果量が標本外でも安定して成立する。",
        "next_test": "複数環境・複数スケールで同じ予測を前向きに比較する。",
    })
    out.append({
        "kind": "causal-mechanism",
        "statement": f"{topic}の主要な観測関連の一部は、特定の因果機構によって生じている可能性がある。",
        "falsifier": "時間順序・介入・自然実験で機構固有の予測が再現しない。",
        "next_test": "競合機構ごとに異なる事前予測を定め、介入または準実験で比較する。",
    })

    dedup = []
    seen = set()
    for h in out:
        key = h["statement"]
        if key and key not in seen:
            seen.add(key)
            dedup.append(h)
    return dedup[:4]


def _voi(row: dict) -> float:
    priority = float(row.get("priority_score", 0.0) or 0.0)
    papers = int(row.get("paper_count", 0) or 0)
    abstracts = int(row.get("abstract_count", 0) or 0)
    updates = int(row.get("post_publication_update_records", 0) or 0)
    kind = _question_kind(row)
    kind_weight = KIND_WEIGHT.get(kind, 0.72)
    evidence_access = abstracts / max(1, papers)
    return round(
        kind_weight
        * (0.60 * priority + 0.18 * math.log1p(papers) + 0.12 * evidence_access + 0.10 * math.log1p(updates)),
        4,
    )


def build_cycles(frontier: dict, limit: int = 30) -> dict:
    cycles = []
    for row in (frontier.get("frontier") or [])[: max(1, limit)]:
        kind = _question_kind(row)
        cycle = {
            "topic": str(row.get("topic", "")),
            "question_kind": kind,
            "research_question": _question_text(row),
            "value_of_information": _voi(row),
            "frontier_priority": float(row.get("priority_score", 0.0) or 0.0),
            "paper_count": int(row.get("paper_count", 0) or 0),
            "abstract_count": int(row.get("abstract_count", 0) or 0),
            "hypotheses": _base_hypotheses(row),
            "source_dois": _source_dois(row),
            "targeted_evidence": {
                "searched": False,
                "papers_screened": 0,
                "abstracts_available": 0,
                "question_kind_resolved_in": 0,
                "question_kind_unresolved_in": 0,
                "update_flags": 0,
                "sample_dois": [],
            },
            "phase": "evidence-needed",
            "epistemic_status": "provisional research cycle; not verified fact",
        }
        cycles.append(cycle)

    cycles.sort(key=lambda x: (-x["value_of_information"], -x["paper_count"], x["topic"]))
    return {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "papers_processed_in_frontier": int(frontier.get("papers_processed", 0) or 0),
        "frontier_cluster_count": int(frontier.get("cluster_count", 0) or 0),
        "cycle_count": len(cycles),
        "cycles": cycles,
        "note": (
            "These cycles prioritize falsifiable follow-up. Targeted literature hits are "
            "screening signals, not proof that a hypothesis is true or false."
        ),
    }


def enrich_targeted_evidence(
    program: dict,
    *,
    days: int,
    papers_per_topic: int,
    topics: int,
    mailto: str,
) -> None:
    appraiser = CriticalAppraiser()
    harvester = CrossrefHarvester(mailto=mailto, rows=min(200, max(20, papers_per_topic)))
    today = dt.date.today()
    start = (today - dt.timedelta(days=max(30, days))).isoformat()
    until = today.isoformat()

    for cycle in program.get("cycles", [])[: max(1, topics)]:
        topic = str(cycle.get("topic", "")).strip()
        if not topic:
            continue
        kind = str(cycle.get("question_kind", "open_question"))
        stats = Counter()
        sample_dois = []
        try:
            for item in harvester.iter_works(
                start,
                until,
                max_works=max(1, papers_per_topic),
                query=topic,
                date_mode="pub",
            ):
                review = appraiser.review(item, store_abstract=False)
                stats["papers"] += 1
                stats["abstracts"] += int(review.abstract_available)
                stats["updates"] += int(bool(review.update_flags))
                by_kind = {q["kind"]: bool(q["resolved"]) for q in review.review_questions}
                if by_kind.get(kind):
                    stats["resolved_kind"] += 1
                else:
                    stats["unresolved_kind"] += 1
                if review.doi and len(sample_dois) < 20:
                    sample_dois.append(review.doi)
        except Exception as exc:
            cycle["targeted_evidence"] = {
                **cycle["targeted_evidence"],
                "searched": True,
                "error": str(exc)[:240],
            }
            continue

        cycle["targeted_evidence"] = {
            "searched": True,
            "from_date": start,
            "until_date": until,
            "papers_screened": stats["papers"],
            "abstracts_available": stats["abstracts"],
            "question_kind_resolved_in": stats["resolved_kind"],
            "question_kind_unresolved_in": stats["unresolved_kind"],
            "update_flags": stats["updates"],
            "sample_dois": sample_dois,
        }

        resolved = stats["resolved_kind"]
        unresolved = stats["unresolved_kind"]
        if stats["papers"] == 0:
            cycle["phase"] = "evidence-sparse"
        elif resolved >= max(3, unresolved):
            cycle["phase"] = "literature-signal-found"
        else:
            cycle["phase"] = "evidence-still-ambiguous"


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn a research frontier into falsifiable autonomous research cycles.")
    ap.add_argument("--frontier", default="literature-review/research_frontier.json")
    ap.add_argument("--output", default="literature-review/research_cycles.json")
    ap.add_argument("--snapshot-output", default="")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--targeted-search", action="store_true")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--topics", type=int, default=20)
    ap.add_argument("--papers-per-topic", type=int, default=60)
    ap.add_argument("--mailto", default=os.environ.get("CROSSREF_MAILTO", ""))
    args = ap.parse_args()

    frontier = json.loads(Path(args.frontier).read_text(encoding="utf-8"))
    program = build_cycles(frontier, max(1, args.limit))

    if args.targeted_search:
        enrich_targeted_evidence(
            program,
            days=max(30, args.days),
            papers_per_topic=max(10, args.papers_per_topic),
            topics=max(1, args.topics),
            mailto=args.mailto,
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(program, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.snapshot_output:
        snap = Path(args.snapshot_output)
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(json.dumps(program, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "cycle_count": program["cycle_count"],
        "targeted_search": bool(args.targeted_search),
        "top_cycles": [
            {
                "topic": c["topic"],
                "research_question": c["research_question"],
                "value_of_information": c["value_of_information"],
                "phase": c["phase"],
                "papers_screened": c["targeted_evidence"]["papers_screened"],
            }
            for c in program["cycles"][:10]
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
