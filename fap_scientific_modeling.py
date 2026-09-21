from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from fap_knowledge_retrieval import terms


@dataclass(frozen=True)
class ScientificModel:
    model_id: str
    title: str
    domain: str
    aliases: tuple[str, ...]
    variables: tuple[str, ...]
    drivers: tuple[str, ...]
    equations: tuple[str, ...]
    mechanism: tuple[str, ...]
    scales: tuple[str, ...]
    assumptions: tuple[str, ...]
    observables: tuple[str, ...]
    limits: tuple[str, ...]


@dataclass(frozen=True)
class ModelMatch:
    model: ScientificModel
    score: float


@dataclass(frozen=True)
class ScienceUpdate:
    update_id: str
    title: str
    domain: str
    topics: tuple[str, ...]
    as_of: str
    source_title: str
    source_url: str
    institution: str
    evidence_type: str
    claim: str


@dataclass(frozen=True)
class ScienceUpdateMatch:
    update: ScienceUpdate
    score: float


EXPLAIN_CUES = re.compile(
    r"(解説|説明|どう動|動き方|仕組み|メカニズム|なぜ|どうして|"
    r"式で|方程式|モデル|どう考え|what happens|how does|explain|mechanism)",
    re.I,
)
EQUATION_CUES = re.compile(r"(式|方程式|数式|equation|formula)", re.I)
WHY_CUES = re.compile(r"(なぜ|どうして|原因|why)", re.I)
LIMIT_CUES = re.compile(r"(限界|不確実|予測でき|どこまで|誤差|limit|uncertain|predict)", re.I)
OBSERVE_CUES = re.compile(r"(観測|測定|何を見|何を測|observe|measure)", re.I)
SCALE_CUES = re.compile(r"(スケール|規模|高度|時間|局地|大規模|scale)", re.I)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


class ScientificModelLibrary:
    """Loads structured scientific models from knowledge/*.jsonl.

    The router does not know individual topics. New models are data records.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self._models: list[ScientificModel] | None = None

    def _load(self) -> list[ScientificModel]:
        path = self.root / "knowledge" / "scientific_models_ja.jsonl"
        if not path.exists():
            return []
        out: list[ScientificModel] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            mid = str(row.get("id", "")).strip()
            title = str(row.get("title", "")).strip()
            if not mid or not title:
                continue
            out.append(ScientificModel(
                model_id=mid,
                title=title,
                domain=str(row.get("domain", "science")),
                aliases=tuple(str(x) for x in row.get("aliases", []) if str(x)),
                variables=tuple(str(x) for x in row.get("variables", []) if str(x)),
                drivers=tuple(str(x) for x in row.get("drivers", []) if str(x)),
                equations=tuple(str(x) for x in row.get("equations", []) if str(x)),
                mechanism=tuple(str(x) for x in row.get("mechanism", []) if str(x)),
                scales=tuple(str(x) for x in row.get("scales", []) if str(x)),
                assumptions=tuple(str(x) for x in row.get("assumptions", []) if str(x)),
                observables=tuple(str(x) for x in row.get("observables", []) if str(x)),
                limits=tuple(str(x) for x in row.get("limits", []) if str(x)),
            ))
        return out

    @property
    def models(self) -> list[ScientificModel]:
        if self._models is None:
            self._models = self._load()
        return self._models

    @staticmethod
    def _score(query: str, model: ScientificModel, context: str = "") -> float:
        qt = terms(query)
        ct = terms(context)
        text = " ".join((model.title, " ".join(model.aliases), " ".join(model.variables), " ".join(model.drivers)))
        mt = terms(text)
        if not mt:
            return 0.0
        overlap = len(qt & mt) / max(1.0, math.sqrt(len(qt) * len(mt))) if qt else 0.0
        context_overlap = len(ct & mt) / max(1.0, math.sqrt(len(ct) * len(mt))) if ct else 0.0
        title_bonus = 0.0
        nq = _norm(query)
        for alias in (model.title,) + model.aliases:
            a = _norm(alias)
            if a and a in nq:
                title_bonus = max(title_bonus, min(0.5, 0.20 + len(a) / 30.0))
        return overlap + 0.30 * context_overlap + title_bonus

    def match(self, query: str, context: str = "") -> ModelMatch | None:
        ranked = [(self._score(query, m, context), m) for m in self.models]
        ranked.sort(key=lambda x: (-x[0], x[1].model_id))
        if not ranked or ranked[0][0] < 0.10:
            return None
        score, model = ranked[0]
        return ModelMatch(model, round(score, 4))


class RecentScienceIndex:
    """Loads dated science updates as evidence data, not routing logic."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._updates: list[ScienceUpdate] | None = None

    def _load(self) -> list[ScienceUpdate]:
        folder = self.root / "knowledge"
        out: list[ScienceUpdate] = []
        if not folder.exists():
            return out
        for path in sorted(folder.glob("latest_science_*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                uid = str(row.get("id", "")).strip()
                claim = str(row.get("claim", "")).strip()
                if not uid or not claim:
                    continue
                out.append(ScienceUpdate(
                    update_id=uid,
                    title=str(row.get("title", uid)),
                    domain=str(row.get("domain", "science")),
                    topics=tuple(str(x) for x in row.get("topics", []) if str(x)),
                    as_of=str(row.get("as_of", "")),
                    source_title=str(row.get("source_title", "")),
                    source_url=str(row.get("source_url", "")),
                    institution=str(row.get("institution", "")),
                    evidence_type=str(row.get("evidence_type", "update")),
                    claim=claim,
                ))
        return out

    @property
    def updates(self) -> list[ScienceUpdate]:
        if self._updates is None:
            self._updates = self._load()
        return self._updates

    @staticmethod
    def _score(query: str, model: ScientificModel, update: ScienceUpdate) -> float:
        q = terms(query)
        mt = terms(" ".join((model.title, model.domain, " ".join(model.aliases))))
        ut = terms(" ".join((update.title, update.domain, " ".join(update.topics), update.claim)))
        if not ut:
            return 0.0
        q_overlap = len(q & ut) / max(1.0, math.sqrt(max(1, len(q)) * len(ut))) if q else 0.0
        model_overlap = len(mt & ut) / max(1.0, math.sqrt(max(1, len(mt)) * len(ut))) if mt else 0.0
        domain_bonus = 0.12 if update.domain == model.domain else 0.0
        recency_bonus = 0.08 if update.as_of >= "2026-01-01" else 0.04
        return q_overlap + 0.55 * model_overlap + domain_bonus + recency_bonus

    def relevant(self, query: str, model: ScientificModel, limit: int = 3) -> list[ScienceUpdateMatch]:
        ranked = [
            (self._score(query, model, update), update)
            for update in self.updates
        ]
        ranked.sort(key=lambda x: (-x[0], x[1].as_of, x[1].update_id), reverse=False)
        # Re-sort explicitly for newest date on equal score.
        ranked = sorted(ranked, key=lambda x: (-x[0], x[1].as_of), reverse=False)
        out = []
        for score, update in ranked:
            if score < 0.10:
                continue
            out.append(ScienceUpdateMatch(update, round(score, 4)))
            if len(out) >= max(1, int(limit)):
                break
        return out


class ScientificModelComposer:
    """Composes mechanism/equation explanations from retrieved model data.

    This is intentionally generic. Adding a model record changes coverage
    without adding topic-specific branches in the chat router.
    """

    def __init__(self, root: Path):
        self.library = ScientificModelLibrary(root)
        self.recent_science = RecentScienceIndex(root)

    @staticmethod
    def _history_context(history: list[Mapping], limit: int = 6) -> str:
        rows = []
        for row in history[-limit:]:
            if row.get("role") not in {"user", "assistant"}:
                continue
            value = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
            if value:
                rows.append(value[:500])
        return " ".join(rows)

    @staticmethod
    def _fmt(items: tuple[str, ...], limit: int) -> str:
        return "".join(f"{x if x.endswith('。') else x + '。'}" for x in items[:limit])

    def _render(self, model: ScientificModel, query: str) -> tuple[str, str]:
        mode = "overview"

        if EQUATION_CUES.search(query):
            mode = "equations"
            reply = (
                f"{model.title}は、変数 {', '.join(model.variables[:7])} を結び付ける系として考えられます。"
                + self._fmt(model.equations, 6)
                + self._fmt(model.mechanism, 3)
            )
        elif LIMIT_CUES.search(query):
            mode = "limits"
            reply = (
                f"{model.title}の仕組み自体はモデル化できます。"
                + self._fmt(model.limits, 5)
                + self._fmt(model.assumptions, 3)
            )
        elif OBSERVE_CUES.search(query):
            mode = "observables"
            reply = (
                f"{model.title}を確かめるには、主に {', '.join(model.observables[:10])} を観測します。"
                + self._fmt(model.mechanism, 3)
                + self._fmt(model.limits, 2)
            )
        elif SCALE_CUES.search(query):
            mode = "scales"
            reply = (
                f"{model.title}はスケールによって支配的な要因が変わります。"
                + self._fmt(model.scales, 5)
                + self._fmt(model.mechanism, 2)
            )
        elif WHY_CUES.search(query):
            mode = "why"
            reply = (
                f"{model.title}が生じる主因は、{', '.join(model.drivers[:8])}です。"
                + self._fmt(model.mechanism, 5)
            )
        else:
            reply = (
                f"{model.title}は、{', '.join(model.drivers[:8])}の相互作用として説明できます。"
                + self._fmt(model.mechanism, 5)
                + (f"代表的な式は {model.equations[0]}。" if model.equations else "")
            )
        return reply, mode

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        t = str(text or "").strip()
        if not t or not EXPLAIN_CUES.search(t):
            return None

        context = self._history_context(history)
        match = self.library.match(t, context)
        if match is None:
            return None

        reply, mode = self._render(match.model, t)

        recent = self.recent_science.relevant(t, match.model, 3)
        if recent:
            latest_text = "最新の取得済み科学見地として、" + "".join(
                f"[{m.update.as_of} {m.update.institution}] {m.update.claim}"
                for m in recent[:2]
            )
            reply += latest_text

        return {
            "ok": True,
            "reply": reply,
            "confidence": round(min(0.98, 0.82 + match.score * 0.12), 3),
            "needs_teacher": False,
            "local": True,
            "scientific_model": True,
            "model_id": match.model.model_id,
            "model_title": match.model.title,
            "model_domain": match.model.domain,
            "model_mode": mode,
            "model_match_score": match.score,
            "model_variables": list(match.model.variables),
            "model_equations": list(match.model.equations),
            "model_assumptions": list(match.model.assumptions),
            "model_limits": list(match.model.limits),
            "recent_science": [
                {
                    "id": m.update.update_id,
                    "as_of": m.update.as_of,
                    "institution": m.update.institution,
                    "source_title": m.update.source_title,
                    "source_url": m.update.source_url,
                    "evidence_type": m.update.evidence_type,
                    "claim": m.update.claim,
                    "match_score": m.score,
                }
                for m in recent
            ],
            "science_snapshot_as_of": max(
                (m.update.as_of for m in recent),
                default="",
            ),
        }
