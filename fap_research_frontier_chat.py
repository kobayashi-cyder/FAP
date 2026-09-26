from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

from fap_knowledge_retrieval import terms


FRONTIER_CUES = re.compile(
    r"(未解決|研究課題|何が分かっていない|何がわかっていない|"
    r"フロンティア|残っている問題|残る問題|次に調べ|次の研究|"
    r"open question|research frontier|unresolved problem)",
    re.I,
)


def _sim(a: str, b: str) -> float:
    aa, bb = terms(a), terms(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))


class ResearchFrontierOrgan:
    """Reads the generated research-frontier snapshot.

    The snapshot is derived from large-scale literature screening. It is a
    prioritization aid, not a declaration that every missing abstract field is
    an established scientific unknown.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.snapshot_path = self.root / "knowledge" / "research_frontier_latest.json"
        self._mtime = None
        self._cache: dict | None = None

    def _load(self) -> dict | None:
        if not self.snapshot_path.exists():
            return None
        try:
            mtime = self.snapshot_path.stat().st_mtime_ns
            if self._cache is not None and self._mtime == mtime:
                return self._cache
            data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("frontier"), list):
                return None
            self._cache = data
            self._mtime = mtime
            return data
        except Exception:
            return None

    @staticmethod
    def _history_context(history: list[Mapping], limit: int = 5) -> str:
        rows = []
        for row in history[-limit:]:
            if row.get("role") not in {"user", "assistant"}:
                continue
            value = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
            if value:
                rows.append(value[:400])
        return " ".join(rows)

    def _rank(self, query: str, history: list[Mapping], rows: list[dict]) -> list[dict]:
        context = self._history_context(history)
        q = query + " " + context
        ranked = []
        generic = len(terms(query)) <= 4
        for row in rows:
            topic = str(row.get("topic", ""))
            questions = " ".join(
                str(x.get("question", "")) for x in row.get("research_questions", [])[:8]
            )
            sim = _sim(q, topic + " " + questions)
            priority = float(row.get("priority_score", 0.0) or 0.0)
            score = priority if generic else (1.5 * sim + 0.20 * priority)
            ranked.append((score, row))
        ranked.sort(key=lambda x: (-x[0], str(x[1].get("topic", ""))))
        return [row for _, row in ranked]

    @staticmethod
    def _render(snapshot: dict, selected: list[dict]) -> str:
        lines = [
            "最新の自動研究フロンティアから、未解決候補を優先度順に出します。",
            "これは文献スクリーニングから作った研究優先度であり、未記載=科学的に未解決と断定しているわけではありません。",
        ]
        for i, row in enumerate(selected[:5], 1):
            topic = str(row.get("topic", ""))
            papers = int(row.get("paper_count", 0) or 0)
            questions = row.get("research_questions") or []
            loops = row.get("provisional_hypothesis_falsification_loops") or []
            lines.append(
                f"{i}. {topic}（関連論文 {papers}件 / priority={float(row.get('priority_score',0)):.3f}）"
            )
            for q in questions[:2]:
                lines.append(f"   Q: {q.get('question','')}")
            if loops:
                loop = loops[0]
                lines.append(f"   仮説候補: {loop.get('hypothesis','')}")
                lines.append(f"   反証条件: {loop.get('falsifier','')}")
                lines.append(f"   次の検証: {loop.get('next_test','')}")
        generated = snapshot.get("generated_at", "")
        if generated:
            lines.append(f"snapshot: {generated}")
        return "\n".join(lines)

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        query = str(text or "").strip()
        if not query or not FRONTIER_CUES.search(query):
            return None

        snapshot = self._load()
        if not snapshot:
            return None
        rows = snapshot.get("frontier") or []
        if not rows:
            return None

        selected = self._rank(query, history, rows)[:5]
        return {
            "ok": True,
            "reply": self._render(snapshot, selected),
            "confidence": 0.91,
            "needs_teacher": False,
            "local": True,
            "research_frontier": True,
            "snapshot_generated_at": snapshot.get("generated_at", ""),
            "papers_processed": int(snapshot.get("papers_processed", 0) or 0),
            "cluster_count": int(snapshot.get("cluster_count", 0) or 0),
            "selected_frontier": selected,
            "epistemic_status": snapshot.get(
                "epistemic_status",
                "automated research-priority snapshot; not verified fact",
            ),
        }
