from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


JA = re.compile(r"[一-龥ぁ-んァ-ンー]{2,}")
EN = re.compile(r"[a-z0-9_+\-]{2,}", re.I)
STOP = (
    "について", "に関して", "どういうこと", "どういう意味", "わかりますか",
    "分かりますか", "教えて", "ください", "ですか", "ますか", "それは", "これは",
    "では", "その", "これ", "それ", "とは",
)


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    title: str
    text: str
    source: str
    domain: str = "general"
    live_required: bool = False


@dataclass(frozen=True)
class RetrievalHit:
    chunk: KnowledgeChunk
    score: float


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def terms(text: str) -> set[str]:
    t = normalize(text)
    for x in STOP:
        t = t.replace(x, " ")
    out = set(EN.findall(t))
    for run in JA.findall(t):
        if len(run) <= 2:
            out.add(run)
        else:
            for n in (2, 3):
                out.update(run[i:i+n] for i in range(len(run) - n + 1))
    return {x for x in out if len(x) >= 2}


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?])\s+|[\r\n]+", str(text or ""))
    out = []
    for part in parts:
        value = re.sub(r"\s+", " ", part).strip(" \t-•")
        if len(value) >= 8:
            out.append(value)
    return out or ([str(text).strip()] if str(text).strip() else [])


class RepositoryKnowledgeIndex:
    """Generic local retrieval over data files in the knowledge directory."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._chunks: list[KnowledgeChunk] | None = None
        self._doc_terms: list[set[str]] = []
        self._idf: dict[str, float] = {}

    def _load(self) -> list[KnowledgeChunk]:
        out: list[KnowledgeChunk] = []
        folder = self.root / "knowledge"
        if not folder.exists():
            return out
        for path in sorted(folder.rglob("*.jsonl")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line_no, line in enumerate(lines, 1):
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                body = str(row.get("text", "")).strip()
                if not body:
                    claim = str(row.get("claim", "")).strip()
                    if claim:
                        as_of = str(row.get("as_of", "")).strip()
                        source_title = str(row.get("source_title", "")).strip()
                        source_url = str(row.get("source_url", "")).strip()
                        body = claim
                        if as_of:
                            body += f"\n時点: {as_of}"
                        if source_title:
                            body += f"\n出典: {source_title}"
                        if source_url:
                            body += f"\nURL: {source_url}"
                    else:
                        parts: list[str] = []
                        for key, label in (
                            ("variables", "変数"),
                            ("drivers", "駆動要因"),
                            ("equations", "式"),
                            ("mechanism", "仕組み"),
                            ("scales", "スケール"),
                            ("assumptions", "前提"),
                            ("observables", "観測量"),
                            ("limits", "限界"),
                        ):
                            values = row.get(key)
                            if isinstance(values, list):
                                cleaned = [
                                    str(x).strip()
                                    for x in values
                                    if str(x).strip()
                                ]
                                if cleaned:
                                    parts.append(
                                        label + ": " + " / ".join(cleaned)
                                    )
                        body = "\n".join(parts)
                if len(body) < 16:
                    continue
                rid = str(row.get("id") or f"{path.stem}:{line_no}")
                out.append(KnowledgeChunk(
                    chunk_id=rid,
                    title=str(row.get("title") or rid),
                    text=body,
                    source=str(path.relative_to(self.root)),
                    domain=str(row.get("domain") or "general"),
                    live_required=bool(
                        row.get("live_required", False)
                        or row.get("as_of")
                        or row.get("source_url")
                    ),
                ))
        return out

    def _build(self) -> None:
        chunks = self._load()
        self._chunks = chunks
        self._doc_terms = [terms(c.title + " " + c.text) for c in chunks]
        df: Counter[str] = Counter()
        for row in self._doc_terms:
            df.update(row)
        n = max(1, len(chunks))
        self._idf = {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}

    @property
    def chunks(self) -> list[KnowledgeChunk]:
        if self._chunks is None:
            self._build()
        return self._chunks or []

    def refresh(self) -> None:
        self._chunks = None
        self._doc_terms = []
        self._idf = {}

    def _similarity(self, q: set[str], d: set[str]) -> float:
        common = q & d
        if not common:
            return 0.0
        num = sum(self._idf.get(x, 1.0) for x in common)
        den = sum(self._idf.get(x, 1.0) for x in q) or 1.0
        return (num / den) * 0.92 + min(0.08, len(common) / max(1, len(d)))

    def search(self, query: str, context: str = "", limit: int = 6) -> list[RetrievalHit]:
        chunks = self.chunks
        q = terms(query)
        c = terms(context)
        nq = normalize(query)
        hits: list[RetrievalHit] = []
        for chunk, d in zip(chunks, self._doc_terms):
            score = self._similarity(q, d)
            if c:
                score += 0.28 * self._similarity(c, d)
            title = normalize(chunk.title)
            if title and len(title) >= 2 and title in nq:
                score += 0.22
            if score > 0:
                hits.append(RetrievalHit(chunk, round(score, 6)))
        hits.sort(key=lambda x: (-x.score, x.chunk.chunk_id))
        return hits[:max(1, int(limit))]

    @staticmethod
    def context_from_history(history: list[Mapping], limit: int = 8) -> str:
        rows: list[str] = []
        for row in history[-limit:]:
            if row.get("role") not in {"user", "assistant"}:
                continue
            value = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
            if value:
                rows.append(value[:600])
        return " ".join(rows)
