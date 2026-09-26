from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Mapping

from fap_knowledge_retrieval import RepositoryKnowledgeIndex, terms
from fap_scientific_modeling import ScientificModelLibrary


HYPOTHESIS_CUES = re.compile(
    r"(仮説|可能性|別の説明|競合仮説|原因を考|原因として|なぜそうなる|"
    r"未解決|反証|検証案|予測を立て|どう考える|何があり得る|"
    r"hypothes|alternative explanation|falsif|abduct|possible cause)",
    re.I,
)

NEGATION = re.compile(
    r"(ない|ません|ではない|とは限らない|不可能|否定|"
    r"\bnot\b|\bno\b|\bnever\b|\bwithout\b|\bimpossible\b)",
    re.I,
)


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _sim(a: str, b: str) -> float:
    aa, bb = terms(a), terms(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))


def _short(text: str, n: int = 180) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value if len(value) <= n else value[: n - 1] + "…"


@dataclass
class Hypothesis:
    hypothesis_id: str
    kind: str
    statement: str
    rationale: str
    predictions: list[str]
    falsifiers: list[str]
    observations: list[str]
    evidence_ids: list[str]
    score: float = 0.0
    status: str = "proposed"


class HypothesisLedger:
    """Persistent store for hypotheses.

    Hypotheses remain explicitly provisional. They are never promoted to the
    verified epistemic ledger merely because they were generated repeatedly.
    """

    MAX_ITEMS = 4000

    def __init__(self, root: Path):
        self.dir = Path(root) / "runtime" / "hypotheses"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "ledger.json"
        self._lock = threading.RLock()
        self._cache: dict | None = None

    def _blank(self) -> dict:
        return {"version": 1, "items": [], "stats": {"proposed": 0, "updated": 0}}

    def _load(self) -> dict:
        with self._lock:
            if self._cache is not None:
                return self._cache
            if not self.path.exists():
                self._cache = self._blank()
                return self._cache
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("not an object")
            except Exception:
                data = self._blank()
            if not isinstance(data.get("items"), list):
                data["items"] = []
            if not isinstance(data.get("stats"), dict):
                data["stats"] = {}
            self._cache = data
            return data

    def _save(self) -> None:
        data = self._load()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    @staticmethod
    def _id(statement: str) -> str:
        return hashlib.sha256(_norm(statement).encode("utf-8")).hexdigest()[:18]

    def novelty(self, statement: str) -> float:
        best = 0.0
        for row in self._load()["items"][-800:]:
            best = max(best, _sim(statement, str(row.get("statement", ""))))
        return max(0.0, 1.0 - best)

    def remember(self, topic: str, hypotheses: list[Hypothesis]) -> dict:
        with self._lock:
            data = self._load()
            added = 0
            updated = 0
            for h in hypotheses:
                hid = self._id(h.statement)
                existing = next((x for x in data["items"] if x.get("id") == hid), None)
                if existing is None:
                    row = asdict(h)
                    row.update({
                        "id": hid,
                        "topic": topic,
                        "first_seen": _now(),
                        "last_seen": _now(),
                    })
                    data["items"].append(row)
                    added += 1
                else:
                    existing["score"] = max(float(existing.get("score", 0.0)), float(h.score))
                    existing["last_seen"] = _now()
                    existing["evidence_ids"] = list(dict.fromkeys(
                        list(existing.get("evidence_ids", [])) + list(h.evidence_ids)
                    ))[:32]
                    updated += 1
            data["items"] = data["items"][-self.MAX_ITEMS:]
            data["stats"]["proposed"] = int(data["stats"].get("proposed", 0)) + added
            data["stats"]["updated"] = int(data["stats"].get("updated", 0)) + updated
            self._save()
            return {"added": added, "updated": updated, "total": len(data["items"])}

    def stats(self) -> dict:
        data = self._load()
        return {
            "items": len(data["items"]),
            "proposed": int(data["stats"].get("proposed", 0)),
            "updated": int(data["stats"].get("updated", 0)),
        }


class HypothesisEngine:
    """Generic abductive reasoning over retrieved knowledge and scientific models.

    It creates competing hypotheses, derives predictions and explicit
    falsification tests, scores novelty/support/falsifiability, and persists the
    proposals separately from verified knowledge.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.index = RepositoryKnowledgeIndex(root)
        self.models = ScientificModelLibrary(root)
        self.ledger = HypothesisLedger(root)

    @staticmethod
    def _context(history: list[Mapping], limit: int = 8) -> str:
        rows = []
        for row in history[-limit:]:
            if row.get("role") not in {"user", "assistant"}:
                continue
            value = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
            if value:
                rows.append(value[:500])
        return " ".join(rows)

    @staticmethod
    def _topic(query: str, hits) -> str:
        if hits:
            return hits[0].chunk.title
        value = re.sub(r"\s+", " ", query).strip(" ?？。")
        return value[:60] or "対象"

    def _scientific_model(self, query: str, context: str):
        ranked = []
        for model in self.models.models:
            mt = terms(" ".join((model.title, " ".join(model.aliases), " ".join(model.drivers), " ".join(model.variables))))
            qt = terms(query)
            ct = terms(context)
            score = 0.0
            if qt and mt:
                score += len(qt & mt) / max(1.0, math.sqrt(len(qt) * len(mt)))
            if ct and mt:
                score += 0.20 * len(ct & mt) / max(1.0, math.sqrt(len(ct) * len(mt)))
            nq = _norm(query)
            if any(_norm(a) in nq for a in (model.title,) + model.aliases if _norm(a)):
                score += 0.35
            ranked.append((score, model))
        ranked.sort(key=lambda x: (-x[0], x[1].model_id))
        return ranked[0][1] if ranked and ranked[0][0] >= 0.08 else None

    @staticmethod
    def _candidate_id(kind: str, statement: str) -> str:
        raw = f"{kind}\n{_norm(statement)}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def _build_candidates(self, query: str, context: str, hits, model) -> list[Hypothesis]:
        topic = self._topic(query, hits)
        evidence_ids = [h.chunk.chunk_id for h in hits[:6]]

        drivers = list(model.drivers[:8]) if model else []
        variables = list(model.variables[:8]) if model else []
        mechanisms = list(model.mechanism[:6]) if model else []
        scales = list(model.scales[:4]) if model else []
        limits = list(model.limits[:4]) if model else []

        if not drivers:
            # Generic fallback: related titles are treated only as candidate
            # explanatory factors, never as verified causal facts.
            drivers = [h.chunk.title for h in hits[1:6] if h.chunk.title != topic]
        if not drivers:
            drivers = ["未観測の入力条件", "境界条件", "測定・モデル誤差"]

        primary = drivers[0]
        secondary = drivers[1] if len(drivers) > 1 else "別の要因"
        variable = variables[0] if variables else "主要な観測量"

        templates = [
            (
                "dominant-driver",
                f"{topic}の観測された振る舞いは、条件によっては「{primary}」の寄与が他要因より支配的になることで説明できる可能性がある。",
                f"既知の候補要因の中で {primary} を優先した単純仮説。",
                [
                    f"{primary}が強い条件ほど、{variable}の変化も系統的に大きくなる。",
                    f"{primary}を弱めた条件では、同じ振る舞いが弱くなる。",
                ],
                [
                    f"{primary}の変化と{variable}が独立なら、この仮説は弱くなる。",
                    f"{primary}を制御しても結果が変わらなければ、支配要因仮説は棄却候補になる。",
                ],
                [f"{primary}と{variable}を同時測定する。", "条件を層別化して効果量を比較する。"],
            ),
            (
                "interaction",
                f"{topic}は単一要因ではなく「{primary}」と「{secondary}」の相互作用で説明した方がよい可能性がある。",
                "単独効果ではなく組み合わせ効果を候補にする。",
                [
                    f"{primary}と{secondary}が同時に強い条件で非加算的な変化が現れる。",
                    "片方だけを変えた場合と両方を変えた場合で結果が一致しない。",
                ],
                [
                    "二要因の交互作用項が不要なら、この仮説の必要性は下がる。",
                    "単一要因モデルが同等以上に外部検証できれば、この仮説は不利になる。",
                ],
                [f"{primary}×{secondary}の条件を分けて測定する。", "交互作用を含むモデルと含まないモデルを比較する。"],
            ),
            (
                "regime-change",
                f"{topic}ではスケールや境界条件が変わると、支配機構そのものが切り替わる可能性がある。",
                scales[0] if scales else "多くの複雑系では支配機構がスケール依存になり得る。",
                [
                    "時間・空間スケールを変えると、同じ説明式の残差構造が変わる。",
                    "ある範囲を境に最適な説明変数が入れ替わる。",
                ],
                [
                    "広いスケール範囲で同一モデル・同一係数が一貫して説明できれば、この仮説は弱くなる。",
                ],
                ["複数スケールで同じ観測量を取得する。", "変化点・レジーム切替を統計的に検定する。"],
            ),
            (
                "omitted-variable",
                f"{topic}の説明不足は、現在のモデルに入っていない変数または観測されていない条件の影響である可能性がある。",
                limits[0] if limits else "取得済み知識だけでは説明し切れない残差を未知要因候補として扱う。",
                [
                    "既存モデルの残差が特定条件で系統的に偏る。",
                    "追加変数を入れると標本外予測が改善する。",
                ],
                [
                    "残差がランダムで追加変数が標本外性能を改善しなければ、この仮説は弱くなる。",
                ],
                ["残差と未使用観測量の関連を調べる。", "追加変数あり/なしで外部検証する。"],
            ),
            (
                "measurement-model-error",
                f"{topic}で見えている異常や不一致の一部は、実在する新機構ではなく測定誤差・初期値誤差・モデル近似で生じている可能性がある。",
                limits[1] if len(limits) > 1 else "新しい実体を仮定する前に観測・モデル誤差を競合仮説として残す。",
                [
                    "独立測定や高解像度モデルでは異常が縮小する。",
                    "誤差の大きい条件ほど不一致が大きくなる。",
                ],
                [
                    "独立手法でも同じ不一致が再現され、誤差低減後も残るならこの仮説は弱くなる。",
                ],
                ["独立センサー・独立データで再測定する。", "解像度・初期値・モデル構造を変えた感度分析を行う。"],
            ),
        ]

        out = []
        for kind, statement, rationale, predictions, falsifiers, observations in templates:
            hid = self._candidate_id(kind, statement)
            novelty = self.ledger.novelty(statement)
            evidence_support = max((float(h.score) for h in hits[:5]), default=0.0)
            falsifiability = 1.0 if falsifiers and observations else 0.5
            parsimony = 0.9 if kind in {"dominant-driver", "measurement-model-error"} else 0.75
            score = min(
                1.0,
                0.34 * evidence_support
                + 0.28 * novelty
                + 0.24 * falsifiability
                + 0.14 * parsimony,
            )
            out.append(Hypothesis(
                hypothesis_id=hid,
                kind=kind,
                statement=statement,
                rationale=rationale,
                predictions=predictions,
                falsifiers=falsifiers,
                observations=observations,
                evidence_ids=evidence_ids,
                score=round(score, 4),
            ))

        # Keep mechanisms available as grounding notes without converting them
        # into extra topic-specific hypotheses.
        if mechanisms:
            for h in out:
                h.rationale = _short(h.rationale + " 既知の機構候補: " + " / ".join(mechanisms[:2]), 360)

        out.sort(key=lambda h: (-h.score, h.kind))
        return out

    @staticmethod
    def _reply(topic: str, hypotheses: list[Hypothesis]) -> str:
        lines = [
            f"{topic}について、競合する仮説を生成し、反証条件まで付けます。",
            "以下は『事実』ではなく、検証候補です。",
        ]
        for i, h in enumerate(hypotheses[:5], 1):
            lines.append(
                f"{i}. 仮説: {h.statement}\n"
                f"   予測: {h.predictions[0]}\n"
                f"   反証: {h.falsifiers[0]}\n"
                f"   次の観測: {h.observations[0]}\n"
                f"   score={h.score:.3f}"
            )
        lines.append("最も重要なのは、支持例を集めるだけでなく、各仮説が失敗する条件を先に決めることです。")
        return "\n".join(lines)

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        query = str(text or "").strip()
        if len(query) < 2 or not HYPOTHESIS_CUES.search(query):
            return None

        context = self._context(history)
        hits = self.index.search(query, context, 10)
        model = self._scientific_model(query, context)
        if not hits and model is None:
            return None

        topic = self._topic(query, hits)
        hypotheses = self._build_candidates(query, context, hits, model)
        if not hypotheses:
            return None

        memory = self.ledger.remember(topic, hypotheses)
        return {
            "ok": True,
            "reply": self._reply(topic, hypotheses),
            "confidence": round(min(0.94, 0.72 + hypotheses[0].score * 0.20), 3),
            "needs_teacher": False,
            "local": True,
            "hypothesis_reasoning": True,
            "topic": topic,
            "scientific_model_id": model.model_id if model else "",
            "generated_hypotheses": len(hypotheses),
            "hypotheses": [asdict(h) for h in hypotheses],
            "hypothesis_memory": memory,
            "verified_fact_promotion": False,
        }
