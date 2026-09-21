from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


WORD = re.compile(r"[A-Za-z][A-Za-z0-9\-]{2,}|[一-龥ぁ-んァ-ンー]{2,}")
STOP = {
    "the","and","for","with","from","using","use","study","studies","analysis","effect","effects",
    "based","new","novel","case","review","research","method","methods","model","models","data",
    "towards","toward","between","among","through","under","into","over","after","before","their",
    "this","that","these","those","results","result","evaluation","assessment","approach",
    "研究","解析","分析","評価","方法","モデル","データ","影響","効果","結果","新規","検討",
}

GAP_WEIGHT = {
    "open_question": 1.00,
    "future_test": 0.98,
    "contradiction": 0.97,
    "causality": 0.95,
    "validation": 0.94,
    "robustness": 0.93,
    "limitations": 0.92,
    "generalization": 0.90,
    "confounding": 0.90,
    "bias": 0.88,
    "prospective_prediction": 0.87,
    "uncertainty": 0.86,
    "effect_size": 0.80,
    "statistics": 0.78,
    "mechanism": 0.78,
    "replication": 0.77,
    "scale": 0.75,
    "missing_data": 0.72,
    "data_provenance": 0.70,
}

QUESTION_TEMPLATE = {
    "open_question": "{topic}で明示的に未解決とされている問いは、どの条件で共通し、どの条件で分岐するか？",
    "future_test": "{topic}で次に行うべき決定的な実験・観測は何か？",
    "contradiction": "{topic}で研究間の不一致があるなら、方法・対象・尺度のどれで説明できるか？",
    "causality": "{topic}で相関と因果を分けるには、どの介入・自然実験・時間順序が必要か？",
    "validation": "{topic}の主要主張は独立データや標本外条件で再現するか？",
    "robustness": "{topic}の結論は解析法・前処理・パラメータを変えても保たれるか？",
    "limitations": "{topic}の主要結論が破綻する境界条件は何か？",
    "generalization": "{topic}の知見は別集団・別環境・別スケールへどこまで一般化できるか？",
    "confounding": "{topic}の主要関連を別の未調整要因で説明できないか？",
    "bias": "{topic}の結果を選択・測定・出版バイアスで説明できないか？",
    "prospective_prediction": "{topic}の説明は事後適合だけでなく前向き予測で成立するか？",
    "uncertainty": "{topic}の不確実性は観測誤差・モデル誤差・本質的変動のどれが支配するか？",
    "effect_size": "{topic}の効果は統計的有意差だけでなく実質的に十分大きいか？",
    "statistics": "{topic}の結論は別の妥当な統計モデルでも維持されるか？",
    "mechanism": "{topic}の観測結果を生む機構を、競合する機構からどう識別できるか？",
    "replication": "{topic}の主要結果は独立チーム・独立データで再現できるか？",
    "scale": "{topic}は時間・空間・組織スケールを変えると支配機構が切り替わるか？",
    "missing_data": "{topic}の欠測・除外が結論をどれだけ動かすか？",
    "data_provenance": "{topic}のデータ来歴・品質差が結論差を生んでいないか？",
}


def words(text: str) -> list[str]:
    out = []
    for raw in WORD.findall(str(text or "").lower()):
        w = raw.strip("-")
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        out.append(w)
    return out


def load_reviews(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict) and row.get("title"):
                rows.append(row)
    return rows


def topic_candidates(row: dict, idf: dict[str, float], limit: int = 2) -> list[str]:
    candidates = []
    for subject in row.get("subjects") or []:
        s = re.sub(r"\s+", " ", str(subject)).strip()
        if 3 <= len(s) <= 80:
            candidates.append((3.0, s))

    counts = Counter(words(row.get("title", "")))
    for token, tf in counts.items():
        score = (1.0 + math.log1p(tf)) * idf.get(token, 1.0)
        candidates.append((score, token))

    candidates.sort(key=lambda x: (-x[0], x[1]))
    out = []
    seen = set()
    for _, label in candidates:
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
        if len(out) >= limit:
            break
    return out or ["unclassified"]


def gap_questions(topic: str, counter: Counter, limit: int = 8) -> list[dict]:
    ranked = sorted(
        counter.items(),
        key=lambda kv: (-(GAP_WEIGHT.get(kv[0], 0.55) * math.log1p(kv[1])), kv[0]),
    )
    out = []
    for kind, count in ranked[:limit]:
        template = QUESTION_TEMPLATE.get(kind, "{topic}の未解決な方法論的ギャップをどう縮めるか？")
        out.append({
            "kind": kind,
            "supporting_papers": count,
            "question": template.format(topic=topic),
        })
    return out


def provisional_loops(topic: str, gaps: Counter) -> list[dict]:
    loops = []
    if any(k in gaps for k in ("confounding","bias","validation","robustness","contradiction")):
        loops.append({
            "hypothesis": f"{topic}で見える研究差の一部は、もし差が実在するなら、対象集団・測定法・解析法の違いで説明できる可能性がある。",
            "falsifier": "方法条件をそろえた独立データでも同じ差が再現され、方法差では説明できない。",
            "next_test": "対象・測定・解析条件を層別化し、同一条件内で結果が再現するか比較する。",
        })
    if any(k in gaps for k in ("scale","generalization","limitations","uncertainty")):
        loops.append({
            "hypothesis": f"{topic}では支配機構または効果量がスケール・環境条件によって切り替わる可能性がある。",
            "falsifier": "広い条件範囲で同一モデル・同一効果量が標本外でも維持される。",
            "next_test": "複数スケール・複数環境で同じ指標を測り、変化点と外部妥当性を検証する。",
        })
    if any(k in gaps for k in ("mechanism","causality","prospective_prediction","future_test")):
        loops.append({
            "hypothesis": f"{topic}の主要な関連の一部は、観測相関ではなく特定の因果機構で生じている可能性がある。",
            "falsifier": "時間順序・介入・自然実験で予測された方向の変化が起きない。",
            "next_test": "競合機構ごとに異なる前向き予測を定義し、介入または準実験で比較する。",
        })
    if any(k in gaps for k in ("replication","data_provenance","missing_data","effect_size","statistics")):
        loops.append({
            "hypothesis": f"{topic}の主要結果の一部は、データ来歴・欠測処理・解析選択に敏感である可能性がある。",
            "falsifier": "独立データと複数の妥当な解析仕様で効果方向と大きさが安定して再現する。",
            "next_test": "独立再解析、欠測感度分析、仕様曲線、外部データ再現を行う。",
        })
    return loops[:4]


def build_frontier(reviews: list[dict], max_clusters: int = 200, min_papers: int = 4) -> dict:
    df = Counter()
    for row in reviews:
        df.update(set(words(row.get("title", ""))))
    n = max(1, len(reviews))
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    clusters = defaultdict(lambda: {
        "papers": 0,
        "abstracts": 0,
        "citations": 0,
        "updates": 0,
        "unresolved": Counter(),
        "resolved": Counter(),
        "open_hints": [],
        "limitation_hints": [],
        "claim_hints": [],
        "examples": [],
        "journals": Counter(),
    })

    for row in reviews:
        labels = topic_candidates(row, idf, 2)
        for label in labels:
            c = clusters[label]
            c["papers"] += 1
            c["abstracts"] += int(bool(row.get("abstract_available")))
            c["citations"] += int(row.get("cited_by_count", 0) or 0)
            c["updates"] += int(bool(row.get("update_flags")))
            c["unresolved"].update(row.get("unresolved_kinds") or [])
            c["resolved"].update(row.get("resolved_kinds") or [])
            if row.get("journal"):
                c["journals"][row["journal"]] += 1
            if len(c["examples"]) < 8:
                c["examples"].append({
                    "doi": row.get("doi", ""),
                    "title": row.get("title", ""),
                    "published": row.get("published", ""),
                    "url": row.get("url", ""),
                })
            for key, target, cap in (
                ("open_question_hints", c["open_hints"], 8),
                ("limitation_hints", c["limitation_hints"], 6),
                ("claim_hints", c["claim_hints"], 6),
            ):
                for hint in row.get(key) or []:
                    if hint not in target and len(target) < cap:
                        target.append(hint)

    out = []
    for topic, c in clusters.items():
        if c["papers"] < min_papers:
            continue
        unresolved_total = sum(c["unresolved"].values())
        question_density = unresolved_total / max(1, c["papers"])
        explicit_open = len(c["open_hints"])
        critical_gap = sum(GAP_WEIGHT.get(k, 0.55) * v for k, v in c["unresolved"].items())
        score = (
            0.28 * math.log1p(c["papers"])
            + 0.22 * math.log1p(critical_gap)
            + 0.18 * math.log1p(1 + explicit_open)
            + 0.10 * math.log1p(1 + c["updates"])
            + 0.08 * math.log1p(1 + c["citations"])
            + 0.14 * min(1.0, question_density / 20.0)
        )
        questions = gap_questions(topic, c["unresolved"], 8)
        loops = provisional_loops(topic, c["unresolved"])
        out.append({
            "topic": topic,
            "priority_score": round(score, 4),
            "paper_count": c["papers"],
            "abstract_count": c["abstracts"],
            "post_publication_update_records": c["updates"],
            "citation_count_crossref": c["citations"],
            "unresolved_appraisal_items": unresolved_total,
            "top_unresolved_kinds": c["unresolved"].most_common(12),
            "top_resolved_kinds": c["resolved"].most_common(8),
            "explicit_open_question_hints": c["open_hints"],
            "limitation_hints": c["limitation_hints"],
            "claim_hints": c["claim_hints"],
            "research_questions": questions,
            "provisional_hypothesis_falsification_loops": loops,
            "example_papers": c["examples"],
            "top_journals": c["journals"].most_common(5),
            "epistemic_status": "research-frontier; not verified fact",
        })

    out.sort(key=lambda x: (-x["priority_score"], -x["paper_count"], x["topic"]))
    return {
        "papers_processed": len(reviews),
        "cluster_count": len(out),
        "frontier": out[:max_clusters],
        "note": (
            "Frontier entries are automated literature-screening priorities. "
            "Missing information in abstracts is not itself proof of a scientific unknown. "
            "Hypotheses are provisional and require full-text/empirical validation."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Cluster unresolved literature appraisal into a research frontier.")
    ap.add_argument("--reviews", default="literature-review/reviews.jsonl")
    ap.add_argument("--output", default="literature-review/research_frontier.json")
    ap.add_argument("--snapshot-output", default="")
    ap.add_argument("--snapshot-limit", type=int, default=50)
    ap.add_argument("--max-clusters", type=int, default=200)
    ap.add_argument("--min-papers", type=int, default=4)
    args = ap.parse_args()

    reviews = load_reviews(Path(args.reviews))
    frontier = build_frontier(
        reviews,
        max_clusters=max(10, args.max_clusters),
        min_papers=max(2, args.min_papers),
    )
    Path(args.output).write_text(
        json.dumps(frontier, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if args.snapshot_output:
        limit = max(5, min(100, int(args.snapshot_limit)))
        snapshot = {
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "papers_processed": frontier["papers_processed"],
            "cluster_count": frontier["cluster_count"],
            "generated_from": str(args.reviews),
            "epistemic_status": "automated research-priority snapshot; not verified fact",
            "frontier": [
                {
                    "topic": row["topic"],
                    "priority_score": row["priority_score"],
                    "paper_count": row["paper_count"],
                    "abstract_count": row["abstract_count"],
                    "post_publication_update_records": row["post_publication_update_records"],
                    "unresolved_appraisal_items": row["unresolved_appraisal_items"],
                    "top_unresolved_kinds": row["top_unresolved_kinds"],
                    "research_questions": row["research_questions"],
                    "provisional_hypothesis_falsification_loops": row["provisional_hypothesis_falsification_loops"],
                }
                for row in frontier["frontier"][:limit]
            ],
        }
        snap_path = Path(args.snapshot_output)
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(json.dumps({
        "ok": True,
        "papers_processed": frontier["papers_processed"],
        "cluster_count": frontier["cluster_count"],
        "frontier_returned": len(frontier["frontier"]),
        "top_frontier": [
            {
                "topic": x["topic"],
                "priority_score": x["priority_score"],
                "paper_count": x["paper_count"],
                "research_questions": len(x["research_questions"]),
                "hypothesis_loops": len(x["provisional_hypothesis_falsification_loops"]),
            }
            for x in frontier["frontier"][:10]
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
