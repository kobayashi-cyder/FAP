from __future__ import annotations

from collections import Counter
import re
from pathlib import Path
from typing import Any, Mapping

from fap_knowledge_retrieval import RepositoryKnowledgeIndex


_EXPLAIN = re.compile(
    r"(知って(?:いる|る)こと|知識|教えて|説明|解説|概要|まとめて|"
    r"どういう|とは|について|what do you know|explain|overview|tell me about)",
    re.I,
)
_INVENTORY = re.compile(
    r"(何を知って|どんなことを知って|知識一覧|知識の一覧|"
    r"持っている知識|knowledge inventory|what do you know)",
    re.I,
)
_FRESH = re.compile(
    r"(最新|今日|現在|今の|ニュース|価格|相場|天気|発売|更新|"
    r"latest|today|current|news|price|weather|release)",
    re.I,
)


def _clean_body(text: str, limit: int = 1500) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "…"


class KnowledgeNarrator:
    """Turns FAP's local knowledge store into grounded conversational answers.

    This layer only narrates indexed repository knowledge. It does not promote
    generated prose into new facts, and it marks dated/live-sensitive material
    instead of pretending that cached knowledge is current.
    """

    CONTRACT = "fap.knowledge.narrator.v1"

    def __init__(self, root: Path):
        self.root = Path(root)
        self.index = RepositoryKnowledgeIndex(self.root)

    def inventory(self, limit: int = 24) -> dict[str, Any]:
        chunks = self.index.chunks
        domains = Counter(chunk.domain for chunk in chunks)
        titles: list[str] = []
        seen = set()
        for chunk in chunks:
            title = chunk.title.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            titles.append(title)
            if len(titles) >= max(1, int(limit)):
                break
        return {
            "chunks": len(chunks),
            "domains": dict(sorted(domains.items())),
            "titles": titles,
        }

    def probe(self, text: str, history: list[Mapping] | None = None) -> float:
        query = str(text or "").strip()
        if not query:
            return 0.0
        if _INVENTORY.search(query):
            return 0.92 if self.index.chunks else 0.0

        context = self.index.context_from_history(list(history or []))
        hits = self.index.search(query, context=context, limit=3)
        if not hits:
            return 0.0

        top = float(hits[0].score)
        explicit = bool(_EXPLAIN.search(query))
        if top < (0.30 if explicit else 0.42):
            return 0.0
        return min(0.96, 0.42 + 0.52 * top + (0.12 if explicit else 0.0))

    def run(
        self,
        text: str,
        history: list[Mapping] | None = None,
    ) -> dict[str, Any] | None:
        query = str(text or "").strip()
        if not query:
            return None

        if _INVENTORY.search(query):
            inv = self.inventory()
            if not inv["chunks"]:
                return None
            domain_text = "、".join(
                f"{name}({count})"
                for name, count in inv["domains"].items()
            )
            title_text = "、".join(inv["titles"])
            return {
                "ok": True,
                "reply": (
                    f"FAPのローカル知識には {inv['chunks']} 個の知識断片があります。"
                    f"\n\n分野: {domain_text or '未分類'}"
                    f"\n\n代表トピック: {title_text}"
                    "\n\n必要なトピックを指定すれば、その範囲で説明できます。"
                ),
                "confidence": 0.96,
                "needs_teacher": False,
                "local": True,
                "grounded": True,
                "knowledge_narrator": True,
                "knowledge_contract": self.CONTRACT,
                "knowledge_inventory": inv,
                "evidence_ids": [],
            }

        context = self.index.context_from_history(list(history or []))
        hits = self.index.search(query, context=context, limit=6)
        if not hits:
            return None

        explicit = bool(_EXPLAIN.search(query))
        threshold = 0.30 if explicit else 0.42
        hits = [hit for hit in hits if hit.score >= threshold]
        if not hits:
            return None

        selected = []
        seen_titles = set()
        seen_text = set()
        for hit in hits:
            title_key = hit.chunk.title.strip().casefold()
            text_key = re.sub(r"\s+", " ", hit.chunk.text).strip().casefold()
            if text_key in seen_text:
                continue
            # Keep at most two complementary chunks with the same title.
            same_title_count = sum(
                1
                for row in selected
                if row.chunk.title.strip().casefold() == title_key
            )
            if same_title_count >= 2:
                continue
            seen_titles.add(title_key)
            seen_text.add(text_key)
            selected.append(hit)
            if len(selected) >= 4:
                break

        if not selected:
            return None

        fresh_requested = bool(_FRESH.search(query))
        dated = any(hit.chunk.live_required for hit in selected)
        needs_teacher = bool(fresh_requested and dated)

        rows: list[str] = []
        for i, hit in enumerate(selected, 1):
            chunk = hit.chunk
            body = _clean_body(chunk.text)
            if len(selected) == 1:
                rows.append(body)
            else:
                rows.append(f"{i}. {chunk.title}\n{body}")

        source_rows = []
        for hit in selected:
            source_rows.append({
                "id": hit.chunk.chunk_id,
                "title": hit.chunk.title,
                "source": hit.chunk.source,
                "domain": hit.chunk.domain,
                "score": round(float(hit.score), 4),
                "live_required": bool(hit.chunk.live_required),
            })

        top_score = float(selected[0].score)
        corroboration = min(0.08, 0.02 * max(0, len(selected) - 1))
        confidence = min(0.95, 0.60 + 0.30 * top_score + corroboration)
        if needs_teacher:
            confidence = min(confidence, 0.72)

        prefix = "FAPがローカルで持っている知識では、"
        reply = prefix + "\n\n" + "\n\n".join(rows)
        if dated:
            reply += (
                "\n\n※ 日付付き・外部出典由来の保存知識を含みます。"
                "保存時点以後の変化は別途確認が必要です。"
            )
        if needs_teacher:
            reply += (
                "\n現在・最新の状態を断定するには、外部調査で更新確認が必要です。"
            )

        return {
            "ok": True,
            "reply": reply,
            "confidence": round(confidence, 4),
            "needs_teacher": needs_teacher,
            "local": True,
            "grounded": True,
            "knowledge_narrator": True,
            "knowledge_contract": self.CONTRACT,
            "evidence_ids": [hit.chunk.chunk_id for hit in selected],
            "knowledge_sources": source_rows,
            "answer_coverage": True,
        }
