from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping

from fap_factual_qa import FactualQAOrgan
from fap_generic_derivation import GenericDerivationEngine
from fap_generic_rule_reasoner import GenericRuleReasoner
from fap_knowledge_narrator import KnowledgeNarrator
from fap_reflective_conversation import ReflectiveConversationOrgan
from fap_response_specialists import SafeArithmeticSpecialist
from fap_response_specialists_extra import (
    LinearEquationSpecialist,
    PhysicsNumericSpecialist,
)


_SPLIT = re.compile(
    r"(?:\n+|[。！？!?；;]+|"
    r"(?<=。)\s*|"
    r"\s+(?:そして|それと|さらに|加えて|then|and then)\s+)",
    re.I,
)
_DIRECTIVE = re.compile(
    r"(教えて|説明|解説|求め|計算|解いて|比較|確認|検証|"
    r"とは|について|どうなる|何|なぜ|"
    r"explain|calculate|solve|compare|verify|what|why)",
    re.I,
)
_CODE_FENCE = re.compile(r"```")


def _clip(value: object, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0.0, min(1.0, x))


def _tokens(text: str) -> set[str]:
    value = str(text or "").casefold()
    out = set(re.findall(r"[A-Za-z0-9_]{2,}", value))
    for chunk in re.findall(r"[一-龥ぁ-んァ-ンー]{2,}", value):
        if len(chunk) <= 3:
            out.add(chunk)
        else:
            out.update(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return out


def _relevance(query: str, reply: str) -> float:
    a, b = _tokens(query), _tokens(reply)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a))


@dataclass(frozen=True)
class Subproblem:
    index: int
    text: str


class SubproblemReasoner:
    """Solve separable multi-intent requests with existing read-only organs.

    It never invents a result for an unsolved segment. Each subproblem is sent
    through independent local/verified organs and only the strongest supported
    candidate is retained. Side-effecting tools are deliberately excluded.
    """

    CONTRACT = "fap.subproblem.reasoner.v1"
    MAX_SUBPROBLEMS = 6

    def __init__(self, root: Path):
        self.root = Path(root)
        self.factual = FactualQAOrgan()
        self.knowledge = KnowledgeNarrator(self.root)
        self.rule = GenericRuleReasoner(self.root)
        self.derivation = GenericDerivationEngine(self.root)
        self.reflective = ReflectiveConversationOrgan()
        self.arithmetic = SafeArithmeticSpecialist()
        self.linear = LinearEquationSpecialist()
        self.physics = PhysicsNumericSpecialist()

    @classmethod
    def split(cls, text: str) -> list[Subproblem]:
        raw = str(text or "").strip()
        if not raw or _CODE_FENCE.search(raw):
            return []

        chunks = []
        for part in _SPLIT.split(raw):
            value = re.sub(r"\s+", " ", part).strip(" 、,")
            if len(value) < 3:
                continue
            if value not in chunks:
                chunks.append(value)

        # A comma-only sentence can still contain multiple explicit intents.
        if len(chunks) < 2:
            comma_parts = [
                re.sub(r"\s+", " ", x).strip(" 、,")
                for x in re.split(r"[、,]+", raw)
            ]
            explicit = [x for x in comma_parts if len(x) >= 3 and _DIRECTIVE.search(x)]
            if len(explicit) >= 2:
                chunks = explicit

        if len(chunks) < 2:
            return []

        directive_count = sum(bool(_DIRECTIVE.search(x)) for x in chunks)
        question_count = raw.count("?") + raw.count("？")
        if directive_count < 2 and question_count < 2:
            return []

        return [
            Subproblem(index=i + 1, text=value)
            for i, value in enumerate(chunks[: cls.MAX_SUBPROBLEMS])
        ]

    @staticmethod
    def _candidate_score(segment: str, payload: Mapping[str, Any]) -> float:
        reply = str(payload.get("reply") or "").strip()
        if not reply:
            return -1.0
        confidence = _clip(payload.get("confidence", 0.55), 0.55)
        verified = bool(
            payload.get("verified")
            or payload.get("factual_qa")
            or payload.get("rule_verified")
            or payload.get("derivation_verified")
            or payload.get("linear_equation_verified")
            or payload.get("physics_numeric_verified")
        )
        grounded = bool(payload.get("grounded") or payload.get("local") or verified)
        needs_teacher = bool(payload.get("needs_teacher"))
        return (
            0.48 * confidence
            + 0.24 * float(verified)
            + 0.12 * float(grounded)
            + 0.16 * min(1.0, _relevance(segment, reply) * 2.5)
            - 0.24 * float(needs_teacher)
        )

    def _solve_one(
        self,
        segment: str,
        history: list[Mapping[str, Any]],
    ) -> tuple[str, dict[str, Any]] | None:
        calls = (
            ("factual", lambda: self.factual.run(segment)),
            ("arithmetic", lambda: self.arithmetic.run(segment)),
            ("linear_equation", lambda: self.linear.run(segment)),
            ("physics_numeric", lambda: self.physics.run(segment)),
            ("rule", lambda: self.rule.run(segment, history)),
            ("derivation", lambda: self.derivation.run(segment, history)),
            ("knowledge", lambda: self.knowledge.run(segment, history)),
            ("reflective", lambda: self.reflective.run(segment, history)),
        )
        candidates: list[tuple[float, str, dict[str, Any]]] = []
        for source, fn in calls:
            try:
                out = fn()
            except Exception:
                continue
            if not isinstance(out, Mapping):
                continue
            payload = dict(out)
            if not str(payload.get("reply") or "").strip():
                continue
            score = self._candidate_score(segment, payload)
            if score < 0.20:
                continue
            candidates.append((score, source, payload))

        if not candidates:
            return None
        candidates.sort(
            key=lambda row: (
                -row[0],
                -_clip(row[2].get("confidence", 0.0)),
                row[1],
            )
        )
        _, source, payload = candidates[0]
        return source, payload

    def run(
        self,
        text: str,
        history: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        problems = self.split(text)
        if len(problems) < 2:
            return None

        history_rows = list(history or [])
        solved: list[dict[str, Any]] = []
        unresolved: list[str] = []

        for problem in problems:
            result = self._solve_one(problem.text, history_rows)
            if result is None:
                unresolved.append(problem.text)
                continue
            source, payload = result
            solved.append({
                "index": problem.index,
                "query": problem.text,
                "source": source,
                "payload": payload,
            })

        if len(solved) < 2:
            return None

        solved.sort(key=lambda row: int(row["index"]))
        coverage = len(solved) / len(problems)
        rows = []
        for row in solved:
            reply = str(row["payload"].get("reply") or "").strip()
            rows.append(f"{row['index']}. {reply}")

        if unresolved:
            rows.append(
                "未解決: " + " / ".join(x[:160] for x in unresolved[:3])
            )

        verified_flags = []
        grounded_flags = []
        confidences = []
        sources = []
        for row in solved:
            payload = row["payload"]
            verified_flags.append(bool(
                payload.get("verified")
                or payload.get("factual_qa")
                or payload.get("rule_verified")
                or payload.get("derivation_verified")
                or payload.get("linear_equation_verified")
                or payload.get("physics_numeric_verified")
            ))
            grounded_flags.append(bool(
                payload.get("grounded")
                or payload.get("local")
                or verified_flags[-1]
            ))
            confidences.append(_clip(payload.get("confidence", 0.55), 0.55))
            sources.append(str(row["source"]))

        confidence = sum(confidences) / max(1, len(confidences))
        confidence *= 0.88 + 0.12 * coverage
        all_verified = bool(verified_flags) and all(verified_flags) and not unresolved
        all_grounded = bool(grounded_flags) and all(grounded_flags)

        return {
            "ok": True,
            "reply": "\n\n".join(rows),
            "confidence": round(min(0.985, confidence), 4),
            "verified": all_verified,
            "grounded": all_grounded,
            "local": True,
            "needs_teacher": bool(unresolved),
            "partial": bool(unresolved),
            "subproblem_reasoning": True,
            "subproblem_contract": self.CONTRACT,
            "subproblem_count": len(problems),
            "subproblem_solved": len(solved),
            "subproblem_coverage": round(coverage, 4),
            "subproblem_sources": sources,
            "subproblem_results": [
                {
                    "index": row["index"],
                    "query": row["query"],
                    "source": row["source"],
                    "verified": bool(
                        row["payload"].get("verified")
                        or row["payload"].get("factual_qa")
                        or row["payload"].get("rule_verified")
                        or row["payload"].get("derivation_verified")
                        or row["payload"].get("linear_equation_verified")
                        or row["payload"].get("physics_numeric_verified")
                    ),
                    "confidence": round(
                        _clip(row["payload"].get("confidence", 0.55), 0.55),
                        4,
                    ),
                }
                for row in solved
            ],
            "decision_source": (
                "verified_subproblem_composition"
                if all_verified
                else "grounded_subproblem_composition"
            ),
        }
