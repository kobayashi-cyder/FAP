from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

from fap_knowledge_retrieval import terms


CYCLE_CUES = re.compile(
    r"(研究サイクル|自律研究|研究を進め|未解決.*進め|問い.*進め|"
    r"仮説.*検証|反証.*進め|次の検証|次に何を調べ|次に何を検証|"
    r"research cycle|advance research|test the hypothes|next experiment)",
    re.I,
)


def _sim(a: str, b: str) -> float:
    aa, bb = terms(a), terms(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))


class ResearchCycleOrgan:
    """Reads the latest literature-derived research-cycle snapshot.

    It presents what evidence should be gathered next. It never treats a
    screening signal as experimental confirmation.
    """

    def __init__(self, root: Path):
        self.path = Path(root) / "knowledge" / "research_cycle_latest.json"
        self._mtime = None
        self._cache: dict | None = None

    def _load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            mtime = self.path.stat().st_mtime_ns
            if self._cache is not None and self._mtime == mtime:
                return self._cache
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("cycles"), list):
                return None
            self._cache = data
            self._mtime = mtime
            return data
        except Exception:
            return None

    @staticmethod
    def _context(history: list[Mapping], limit: int = 5) -> str:
        out = []
        for row in history[-limit:]:
            if row.get("role") not in {"user", "assistant"}:
                continue
            value = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
            if value:
                out.append(value[:400])
        return " ".join(out)

    def _rank(self, query: str, history: list[Mapping], cycles: list[dict]) -> list[dict]:
        ctx = self._context(history)
        combined = query + " " + ctx
        generic = len(terms(query)) <= 4
        ranked = []
        for row in cycles:
            topic = str(row.get("topic", ""))
            question = str(row.get("research_question", ""))
            sim = _sim(combined, topic + " " + question)
            voi = float(row.get("value_of_information", 0.0) or 0.0)
            score = voi if generic else (1.7 * sim + 0.20 * voi)
            ranked.append((score, row))
        ranked.sort(key=lambda x: (-x[0], str(x[1].get("topic", ""))))
        return [r for _, r in ranked]

    @staticmethod
    def _render(selected: list[dict], generated_at: str) -> str:
        lines = [
            "研究フロンティアから、次に回すべき仮説→反証→再検証サイクルを出します。",
            "文献スクリーニングの一致は支持シグナルであって、仮説の実証ではありません。",
        ]
        for i, row in enumerate(selected[:3], 1):
            ev = row.get("targeted_evidence") or {}
            lines.append(
                f"{i}. {row.get('topic','')} / VOI={float(row.get('value_of_information',0)):.3f} / phase={row.get('phase','')}"
            )
            lines.append(f"   研究問い: {row.get('research_question','')}")
            lines.append(
                "   文献再検索: "
                f"{int(ev.get('papers_screened',0) or 0)}件、"
                f"該当評価項目あり {int(ev.get('question_kind_resolved_in',0) or 0)}件、"
                f"未確認 {int(ev.get('question_kind_unresolved_in',0) or 0)}件"
            )
            hypotheses = row.get("hypotheses") or []
            for h in hypotheses[:2]:
                lines.append(f"   仮説: {h.get('statement','')}")
                lines.append(f"   反証: {h.get('falsifier','')}")
                lines.append(f"   次の検証: {h.get('next_test','')}")
        if generated_at:
            lines.append(f"snapshot: {generated_at}")
        return "\n".join(lines)

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        query = str(text or "").strip()
        if not query or not CYCLE_CUES.search(query):
            return None
        data = self._load()
        if not data:
            return None
        cycles = data.get("cycles") or []
        if not cycles:
            return None
        selected = self._rank(query, history, cycles)[:3]
        return {
            "ok": True,
            "reply": self._render(selected, str(data.get("generated_at", ""))),
            "confidence": 0.92,
            "needs_teacher": False,
            "local": True,
            "research_cycle": True,
            "generated_at": data.get("generated_at", ""),
            "cycle_count": int(data.get("cycle_count", 0) or 0),
            "papers_processed_in_frontier": int(data.get("papers_processed_in_frontier", 0) or 0),
            "selected_cycles": selected,
            "verified_fact_promotion": False,
        }
