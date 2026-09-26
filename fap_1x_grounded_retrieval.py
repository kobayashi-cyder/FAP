from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from fap_knowledge_retrieval import RepositoryKnowledgeIndex, sentences, terms


@dataclass(frozen=True)
class GroundedRetrievalResult:
    reply: str
    confidence: float
    chunk_ids: tuple[str, ...]
    sources: tuple[str, ...]
    scores: tuple[float, ...]
    live_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GroundedRetrievalReasoner:
    """Conservative extractive local-knowledge lane.

    It returns only sentences already present in the repository knowledge
    corpus. Items marked live_required never become a local final answer.
    """

    MIN_SCORE = 0.48
    MIN_MARGIN = 0.05

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.index = RepositoryKnowledgeIndex(self.root)

    @staticmethod
    def _history_context(history: list[Mapping[str, Any]]) -> str:
        return RepositoryKnowledgeIndex.context_from_history(history, limit=6)

    @staticmethod
    def _sentence_score(query_terms: set[str], text: str) -> float:
        row = terms(text)
        if not query_terms or not row:
            return 0.0
        return len(query_terms & row) / max(1, len(query_terms))

    def probe(
        self,
        text: str,
        history: list[Mapping[str, Any]] | None = None,
    ) -> float:
        context = self._history_context(list(history or []))
        hits = self.index.search(text, context, 2)
        if not hits:
            return 0.0
        first = float(hits[0].score)
        second = float(hits[1].score) if len(hits) > 1 else 0.0
        if hits[0].chunk.live_required:
            return 0.0
        if first < self.MIN_SCORE:
            return 0.0
        if len(hits) > 1 and first - second < self.MIN_MARGIN and first < 0.72:
            return 0.0
        return min(0.90, 0.55 + first * 0.35)

    def run(
        self,
        text: str,
        history: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        query = str(text or "").strip()
        if not query:
            return None
        rows = list(history or [])
        context = self._history_context(rows)
        hits = self.index.search(query, context, 4)
        if not hits:
            return None

        first = hits[0]
        second_score = float(hits[1].score) if len(hits) > 1 else 0.0
        if first.chunk.live_required:
            return {
                "ok": False,
                "reply": "",
                "confidence": 0.0,
                "grounded_retrieval": True,
                "needs_live_retrieval": True,
                "evidence_ids": [first.chunk.chunk_id],
                "evidence_sources": [first.chunk.source],
            }
        if float(first.score) < self.MIN_SCORE:
            return None
        if len(hits) > 1 and float(first.score) - second_score < self.MIN_MARGIN and float(first.score) < 0.72:
            return None

        qterms = terms(query)
        ranked_sentences = []
        for sentence in sentences(first.chunk.text):
            score = self._sentence_score(qterms, sentence)
            ranked_sentences.append((score, sentence))
        ranked_sentences.sort(key=lambda row: (-row[0], len(row[1]), row[1]))
        chosen = [sentence for score, sentence in ranked_sentences if score > 0][:3]
        if not chosen:
            chosen = [first.chunk.text.strip()]

        reply = "\n".join(chosen)
        confidence = min(0.82, 0.48 + float(first.score) * 0.38)
        result = GroundedRetrievalResult(
            reply=reply,
            confidence=confidence,
            chunk_ids=(first.chunk.chunk_id,),
            sources=(first.chunk.source,),
            scores=(float(first.score),),
            live_required=False,
        )
        payload = result.to_dict()
        payload.update(
            {
                "ok": True,
                "local": True,
                "grounded": True,
                "grounded_retrieval": True,
                "needs_live_retrieval": False,
                "evidence_ids": list(result.chunk_ids),
                "evidence_sources": list(result.sources),
            }
        )
        return payload
