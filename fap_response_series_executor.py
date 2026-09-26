from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
import re
from typing import Any, Mapping

from fap_factual_qa import FactualQAOrgan
from fap_generic_derivation import GenericDerivationEngine
from fap_generic_rule_reasoner import GenericRuleReasoner
from fap_reflective_conversation import ReflectiveConversationOrgan
from fap_response_redundancy import ResponseLane, ResponseSeriesPlan
from fap_response_specialists import (
    CausalFrameSpecialist,
    CodePlanningSpecialist,
    ResponseAuditor,
    SafeArithmeticSpecialist,
)
from fap_response_specialists_extra import (
    LinearEquationSpecialist,
    NumericContradictionSpecialist,
    PhysicsNumericSpecialist,
    PythonStaticAnalysisSpecialist,
)
from fap_response_explorers import (
    CausalGraphExplorer,
    CounterexampleConditionExplorer,
    LongFormContradictionExplorer,
    MultiStepMathExplorer,
    PythonRepairExplorer,
)


_JA_OR_WORD = re.compile(r"[一-龥ぁ-んァ-ンー]{2,}|[A-Za-z0-9_]{2,}")
_NUMBER = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_STRUCTURE = re.compile(r"(?:^|\n)\s*(?:[-*•]|\d+[.)、]|[A-Z][.)])\s+", re.M)
_MECHANISM = re.compile(r"(ため|ので|原因|仕組|機構|したがって|because|therefore|mechanism|cause)", re.I)
_BOUNDARY = re.compile(r"(ただし|一方|例外|限界|条件|場合|反例|falsif|counterexample|boundary|limitation)", re.I)
_ALTERNATIVE = re.compile(r"(または|別の|一方|代替|alternative|another|instead)", re.I)
_PROCEDURE = re.compile(r"(手順|まず|次に|最後に|step|procedure|workflow)", re.I)
_ANALOGY = re.compile(r"(たとえば|例えば|例える|analog|for example|e\.g\.)", re.I)
_UNCERTAINTY = re.compile(r"(不明|未解決|可能性|推測|確定でき|根拠不足|uncertain|unknown|may|might)", re.I)


def _clip(value: object, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not isfinite(x):
        return default
    return max(0.0, min(1.0, x))


def _features(text: str) -> set[str]:
    value = str(text or "").casefold()
    out: set[str] = set()
    for token in _JA_OR_WORD.findall(value):
        if re.search(r"[一-龥ぁ-んァ-ンー]", token):
            if len(token) <= 2:
                out.add(token)
            else:
                out.update(token[i : i + 2] for i in range(len(token) - 1))
        else:
            out.add(token)
    return out


def _overlap(a: str, b: str) -> float:
    x = _features(a)
    y = _features(b)
    if not x or not y:
        return 0.0
    return len(x & y) / max(1, len(x | y))


def _reply_key(text: str) -> str:
    return re.sub(r"[\W_]+", "", str(text or "").casefold(), flags=re.UNICODE)


def _verified(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("factual_qa")
        or payload.get("rule_verified")
        or payload.get("derivation_verified")
        or payload.get("verified")
        or payload.get("decision_source") in {"verified_arithmetic", "option_conditioned_science"}
    )


@dataclass
class ResponseCandidate:
    candidate_id: str
    payload: dict[str, Any]
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    verified: bool = False
    grounded: bool = False
    needs_teacher: bool = False
    primary: bool = False
    requirement_coverage: float = 1.0
    segment_coverage: float = 1.0

    @property
    def reply(self) -> str:
        return str(self.payload.get("reply") or "")


class ResponseSeriesExecutor:
    """Make response redundancy affect the selected answer.

    Only read-only/local specialists are invoked here. Artifact generation,
    repository writes, network actions, and other side-effecting endpoints are
    deliberately excluded from redundant execution.
    """

    CONTRACT = "fap.response.series.execution.v1"
    SAFE_SPECIALISTS = (
        "factual",
        "arithmetic",
        "reflective",
        "causal",
        "rule",
        "code_plan",
        "linear_equation",
        "physics_numeric",
        "python_static",
        "contradiction",
        "multi_step_math",
        "python_repair",
        "causal_graph",
        "counterexample_search",
        "longform_contradiction",
        "derivation",
    )

    def __init__(self, root: Path):
        self.root = Path(root)
        self.factual = FactualQAOrgan()
        self.reflective = ReflectiveConversationOrgan()
        self.rule = GenericRuleReasoner(self.root)
        self.derivation = GenericDerivationEngine(self.root)
        self.arithmetic = SafeArithmeticSpecialist()
        self.causal = CausalFrameSpecialist()
        self.code_plan = CodePlanningSpecialist()
        self.linear_equation = LinearEquationSpecialist()
        self.physics_numeric = PhysicsNumericSpecialist()
        self.python_static = PythonStaticAnalysisSpecialist()
        self.contradiction = NumericContradictionSpecialist()
        self.multi_step_math = MultiStepMathExplorer()
        self.python_repair = PythonRepairExplorer()
        self.causal_graph = CausalGraphExplorer()
        self.counterexample_search = CounterexampleConditionExplorer()
        self.longform_contradiction = LongFormContradictionExplorer()
        self.auditor = ResponseAuditor()

    @staticmethod
    def _candidate(source: str, payload: Mapping[str, Any], *, primary: bool = False) -> ResponseCandidate | None:
        if not isinstance(payload, Mapping):
            return None
        data = dict(payload)
        reply = str(data.get("reply") or "").strip()
        if not reply:
            return None
        return ResponseCandidate(
            candidate_id=source,
            payload=data,
            sources=[source],
            confidence=_clip(data.get("confidence", 0.55), 0.55),
            verified=_verified(data),
            grounded=bool(data.get("grounded") or data.get("local") or _verified(data)),
            needs_teacher=bool(data.get("needs_teacher")),
            primary=primary,
        )

    @staticmethod
    def _merge_candidate(existing: ResponseCandidate, new: ResponseCandidate) -> None:
        for source in new.sources:
            if source not in existing.sources:
                existing.sources.append(source)
        existing.confidence = max(existing.confidence, new.confidence)
        existing.verified = existing.verified or new.verified
        existing.grounded = existing.grounded or new.grounded
        existing.needs_teacher = existing.needs_teacher and new.needs_teacher
        existing.primary = existing.primary or new.primary

    def _specialist_results(
        self,
        text: str,
        history: list[Mapping],
        plan: ResponseSeriesPlan,
    ) -> tuple[list[tuple[str, Mapping[str, Any]]], list[dict[str, str]]]:
        calls: list[tuple[str, Any]] = [
            ("factual", lambda: self.factual.run(text)),
            ("arithmetic", lambda: self.arithmetic.run(text)),
            ("reflective", lambda: self.reflective.run(text, history)),
        ]
        if plan.active_lanes >= 10:
            calls.append(("causal", lambda: self.causal.run(text)))
        if plan.active_lanes >= 12:
            calls.append(("rule", lambda: self.rule.run(text, history)))
        if plan.active_lanes >= 14:
            calls.append(("linear_equation", lambda: self.linear_equation.run(text)))
        if plan.active_lanes >= 16:
            calls.append(("code_plan", lambda: self.code_plan.run(text)))
            calls.append(("physics_numeric", lambda: self.physics_numeric.run(text)))
        if plan.active_lanes >= 20:
            calls.append(("python_static", lambda: self.python_static.run(text)))
        if plan.active_lanes >= 24:
            calls.append(("contradiction", lambda: self.contradiction.run(text, history)))
        if plan.active_lanes >= 14:
            calls.append(("multi_step_math", lambda: self.multi_step_math.run(text)))
        if plan.active_lanes >= 20:
            calls.append(("python_repair", lambda: self.python_repair.run(text)))
        if plan.active_lanes >= 24:
            calls.append(("causal_graph", lambda: self.causal_graph.run(text)))
        if plan.active_lanes >= 28:
            calls.append(("counterexample_search", lambda: self.counterexample_search.run(text)))
        if plan.active_lanes >= 32:
            calls.append(("longform_contradiction", lambda: self.longform_contradiction.run(text, history)))
        if plan.active_lanes >= 18:
            calls.append(("derivation", lambda: self.derivation.run(text, history)))

        out: list[tuple[str, Mapping[str, Any]]] = []
        diagnostics: list[dict[str, str]] = []
        for name, fn in calls:
            try:
                result = fn()
            except Exception as exc:
                diagnostics.append({"source": name, "state": "failed", "reason": type(exc).__name__})
                continue
            if isinstance(result, Mapping) and str(result.get("reply") or "").strip():
                out.append((name, result))
                diagnostics.append({"source": name, "state": "candidate", "reason": ""})
            else:
                diagnostics.append({"source": name, "state": "declined", "reason": ""})
        return out, diagnostics

    @staticmethod
    def _base_quality(candidate: ResponseCandidate) -> float:
        score = 0.55 * candidate.confidence
        if candidate.verified:
            score += 0.22
        if candidate.payload.get("linear_equation_verified"):
            score += 0.16
        if candidate.payload.get("physics_numeric_verified"):
            score += 0.14
        if candidate.payload.get("python_static_analysis"):
            score += 0.10
        if candidate.payload.get("numeric_contradiction_verified"):
            score += 0.12
        if candidate.grounded:
            score += 0.08
        if candidate.primary:
            score += 0.03
        if candidate.needs_teacher:
            score -= 0.20
        if len(candidate.reply) < 8:
            score -= 0.20
        score += 0.035 * candidate.requirement_coverage
        score += 0.045 * candidate.segment_coverage
        return score

    def _lane_score(
        self,
        candidate: ResponseCandidate,
        lane: ResponseLane,
        user_text: str,
    ) -> float:
        reply = candidate.reply
        score = self._base_quality(candidate)
        relevance = _overlap(user_text, reply)
        role = lane.role

        if role in {"direct", "user_intent"}:
            score += 0.18 * relevance + 0.08 * candidate.segment_coverage
        elif role == "decomposition":
            score += min(0.12, 0.025 * len(_STRUCTURE.findall(reply)))
        elif role == "assumptions":
            score += 0.06 if re.search(r"(前提|仮定|assum|premise)", reply, re.I) else 0.01 * relevance
        elif role == "mechanism":
            score += 0.08 if _MECHANISM.search(reply) else 0.02 * relevance
        elif role == "evidence":
            score += 0.18 if candidate.verified else (0.06 if candidate.grounded else -0.06)
        elif role == "counterexample":
            score += 0.08 if _BOUNDARY.search(reply) else (0.03 if candidate.verified else 0.0)
        elif role == "constraints":
            score += 0.08 * relevance + 0.12 * candidate.requirement_coverage
            if re.search(r"(必須|条件|制約|must|required|constraint)", user_text, re.I):
                score += 0.04 if re.search(r"(条件|制約|must|required|constraint)", reply, re.I) else -0.03
        elif role == "edge_cases":
            score += 0.08 if _BOUNDARY.search(reply) else 0.0
        elif role == "alternatives":
            score += 0.06 if _ALTERNATIVE.search(reply) else (0.02 if not candidate.primary else 0.0)
        elif role == "procedure":
            score += 0.08 if (_PROCEDURE.search(reply) or _STRUCTURE.search(reply)) else 0.0
        elif role == "analogy":
            score += 0.06 if _ANALOGY.search(reply) else 0.0
        elif role == "uncertainty":
            if candidate.verified:
                score += 0.06
            elif _UNCERTAINTY.search(reply) or candidate.needs_teacher:
                score += 0.04
            elif candidate.confidence > 0.95:
                score -= 0.07
        elif role == "compression":
            n = len(reply)
            if 40 <= n <= 1200:
                score += 0.07
            elif n > 2400:
                score -= 0.06
        elif role == "verifier":
            score += 0.22 if candidate.verified else (0.04 if candidate.grounded else -0.08)
        elif role == "synthesis_probe":
            score += (
                0.10 * candidate.confidence
                + 0.08 * float(candidate.verified)
                + 0.06 * relevance
                + 0.06 * candidate.segment_coverage
                + 0.04 * candidate.requirement_coverage
            )

        if lane.variant:
            if lane.variant % 3 == 1:
                score += 0.05 * relevance
            elif lane.variant % 3 == 2:
                score += 0.04 * candidate.confidence
            else:
                score += 0.035 * float(candidate.verified)

        return score * float(lane.priority)

    @staticmethod
    def _conflict(a: ResponseCandidate, b: ResponseCandidate) -> bool:
        if not (a.verified and b.verified and a.confidence >= 0.85 and b.confidence >= 0.85):
            return False
        if _overlap(a.reply, b.reply) >= 0.20:
            return False
        nums_a = set(_NUMBER.findall(a.reply))
        nums_b = set(_NUMBER.findall(b.reply))
        if nums_a and nums_b and nums_a != nums_b:
            return True
        return len(a.reply) > 24 and len(b.reply) > 24

    @staticmethod
    def _copy_operational_metadata(primary: Mapping[str, Any], selected: dict[str, Any]) -> None:
        for key in ("status", "session", "interaction_dispatch"):
            if key in primary and key not in selected:
                selected[key] = primary[key]

    def run(
        self,
        text: str,
        history: list[Mapping],
        primary_payload: Mapping[str, Any],
        plan: ResponseSeriesPlan,
    ) -> dict[str, Any]:
        primary = self._candidate("primary", primary_payload, primary=True)
        if primary is None:
            primary = ResponseCandidate(
                candidate_id="primary",
                payload=dict(primary_payload),
                sources=["primary"],
                confidence=0.0,
                primary=True,
            )

        candidates: list[ResponseCandidate] = [primary]
        by_reply: dict[str, ResponseCandidate] = {}
        if primary.reply:
            by_reply[_reply_key(primary.reply)] = primary

        specialist_results, diagnostics = self._specialist_results(text, history, plan)
        for source, payload in specialist_results:
            candidate = self._candidate(source, payload)
            if candidate is None:
                continue
            key = _reply_key(candidate.reply)
            if key and key in by_reply:
                self._merge_candidate(by_reply[key], candidate)
                continue
            candidates.append(candidate)
            if key:
                by_reply[key] = candidate

        # Under broad/high-pressure requests, make the synthesis budget concrete:
        # compose complementary, non-teacher read-only candidates rather than
        # merely choosing one of them. The synthesis is deterministic and does
        # not invoke a hidden model or replay side effects.
        if plan.active_lanes >= 32 and len(candidates) >= 3:
            ranked_for_synthesis = sorted(
                (
                    (
                        0.55 * c.confidence
                        + 0.25 * float(c.verified)
                        + 0.20 * _overlap(text, c.reply),
                        c,
                    )
                    for c in candidates
                    if c.reply and not c.needs_teacher
                ),
                key=lambda row: (-row[0], row[1].candidate_id),
            )
            components: list[ResponseCandidate] = []
            component_limit = max(2, min(4, plan.synthesis_width // 4))
            for _, candidate in ranked_for_synthesis:
                if any(_overlap(candidate.reply, prior.reply) >= 0.72 for prior in components):
                    continue
                components.append(candidate)
                if len(components) >= component_limit:
                    break
            if len(components) >= 2:
                payload = {
                    "ok": True,
                    "reply": "\n\n".join(c.reply for c in components),
                    "confidence": min(
                        0.97,
                        sum(c.confidence for c in components) / len(components) + 0.02,
                    ),
                    "verified": all(c.verified for c in components),
                    "grounded": all(c.grounded for c in components),
                    "local": True,
                    "response_synthesis": True,
                }
                synthesis = self._candidate("synthesis", payload)
                if synthesis is not None:
                    synthesis.sources = [
                        source
                        for c in components
                        for source in c.sources
                        if source not in {"synthesis"}
                    ]
                    candidates.append(synthesis)

        for candidate in candidates:
            audit = self.auditor.audit(text, candidate.reply)
            candidate.requirement_coverage = audit.requirement_coverage
            candidate.segment_coverage = audit.segment_coverage

        weighted_votes = {c.candidate_id: 0.0 for c in candidates}
        lane_winners: list[dict[str, Any]] = []
        for lane in plan.lanes:
            ranked = sorted(
                ((self._lane_score(c, lane, text), c) for c in candidates),
                key=lambda row: (-row[0], -row[1].confidence, row[1].candidate_id),
            )
            best_score, best = ranked[0]
            weighted_votes[best.candidate_id] += float(lane.priority)
            lane_winners.append(
                {
                    "lane_id": lane.lane_id,
                    "role": lane.role,
                    "winner": best.candidate_id,
                    "score": round(best_score, 5),
                }
            )

        candidate_scores: dict[str, float] = {}
        for c in candidates:
            own = [
                self._lane_score(c, lane, text)
                for lane in plan.lanes
            ]
            candidate_scores[c.candidate_id] = (
                sum(own) / max(1, len(own))
                + 0.025 * weighted_votes[c.candidate_id]
            )

        all_winner = max(
            candidates,
            key=lambda c: (
                weighted_votes[c.candidate_id],
                candidate_scores[c.candidate_id],
                c.confidence,
                c.verified,
                c.primary,
            ),
        )

        committee_rows = lane_winners[: max(1, min(plan.synthesis_width, len(lane_winners)))]
        committee_counts: dict[str, int] = {}
        for row in committee_rows:
            cid = str(row["winner"])
            committee_counts[cid] = committee_counts.get(cid, 0) + 1
        committee_winner_id = max(
            committee_counts,
            key=lambda cid: (
                committee_counts[cid],
                weighted_votes.get(cid, 0.0),
                candidate_scores.get(cid, 0.0),
            ),
        )
        committee_support = committee_counts[committee_winner_id]
        quorum_met = committee_support >= plan.quorum
        committee_winner = next(c for c in candidates if c.candidate_id == committee_winner_id)

        proposed = all_winner if all_winner.candidate_id == committee_winner.candidate_id else committee_winner

        exact_verified = [
            candidate
            for candidate in candidates
            if candidate.verified
            and candidate.confidence >= 0.95
            and (
                candidate.payload.get("linear_equation_verified")
                or candidate.payload.get("physics_numeric_verified")
                or candidate.payload.get("python_static_analysis")
            )
        ]
        if exact_verified:
            exact_verified.sort(
                key=lambda candidate: (
                    -candidate_scores.get(candidate.candidate_id, 0.0),
                    -candidate.confidence,
                    candidate.candidate_id,
                )
            )
            proposed = exact_verified[0]

        selected = primary

        if proposed.candidate_id != "primary":
            exact_task_verified = bool(
                proposed.payload.get("linear_equation_verified")
                or proposed.payload.get("physics_numeric_verified")
                or proposed.payload.get("python_static_analysis")
            )
            weak_primary = (
                primary.needs_teacher
                or primary.confidence < 0.60
                or not primary.reply
            )
            strong_verified_challenger = (
                proposed.verified
                and not proposed.needs_teacher
                and proposed.confidence >= max(0.82, primary.confidence - 0.03)
            )
            vote_advantage = weighted_votes[proposed.candidate_id] >= (
                weighted_votes["primary"] * (0.95 if proposed.verified and not primary.verified else 1.08)
            )
            if (
                exact_task_verified
                and proposed.verified
                and proposed.confidence >= 0.95
            ) or (weak_primary and proposed.confidence >= 0.65) or (
                quorum_met and strong_verified_challenger and vote_advantage
            ):
                selected = proposed

        disagreements = [
            (a.candidate_id, b.candidate_id)
            for i, a in enumerate(candidates)
            for b in candidates[i + 1 :]
            if self._conflict(a, b)
        ]

        final = dict(selected.payload)
        self._copy_operational_metadata(primary_payload, final)

        tags = [str(x) for x in final.get("route_tags", [])]
        for tag in (
            "response-series-executed",
            "safe-readonly-specialists",
            f"response-selected:{selected.candidate_id}",
        ):
            if tag not in tags:
                tags.append(tag)
        final["route_tags"] = tags

        final["response_series_execution"] = {
            "contract": self.CONTRACT,
            "planned_lanes": plan.active_lanes,
            "executed_lane_votes": len(lane_winners),
            "safe_specialist_calls": len(diagnostics),
            "specialist_diagnostics": diagnostics,
            "candidate_count": len(candidates),
            "candidates": [
                {
                    "id": c.candidate_id,
                    "sources": list(c.sources),
                    "confidence": round(c.confidence, 4),
                    "verified": c.verified,
                    "grounded": c.grounded,
                    "needs_teacher": c.needs_teacher,
                    "requirement_coverage": round(c.requirement_coverage, 4),
                    "segment_coverage": round(c.segment_coverage, 4),
                    "weighted_votes": round(weighted_votes[c.candidate_id], 4),
                    "aggregate_score": round(candidate_scores[c.candidate_id], 5),
                }
                for c in candidates
            ],
            "all_lane_winner": all_winner.candidate_id,
            "committee_winner": committee_winner.candidate_id,
            "committee_support": committee_support,
            "committee_quorum": plan.quorum,
            "quorum_met": quorum_met,
            "selected": selected.candidate_id,
            "selection_changed_primary": selected.candidate_id != "primary",
            "consensus_sources": list(selected.sources),
            "verified_disagreements": [list(x) for x in disagreements],
            "side_effecting_specialists_executed": False,
        }
        return final
