from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any, Mapping

from fap_benchmark_reasoning import StructuredMCQParser, StructuredMCQReasoner
from fap_factual_qa import FactualQAOrgan
from fap_generic_derivation import GenericDerivationEngine
from fap_generic_rule_reasoner import GenericRuleReasoner
from fap_hypothesis_engine import HYPOTHESIS_CUES, HypothesisEngine
from fap_physics_solver_v2 import ExpandedPhysicsSolver
from fap_scientific_reasoning import OptionConditionedScientificReasoner
from fap_1x_algebra_solver import GenericLinearEquationSolver
from fap_1x_candidate_verifier import IndependentCandidateVerifier
from fap_1x_confidence_calibrator import ConfidenceCalibrator
from fap_1x_grounded_retrieval import GroundedRetrievalReasoner
from fap_1x_problem_decomposer import ProblemDecomposer
from fap_1x_search_controller import AdaptiveSearchController


@dataclass(frozen=True)
class ReasoningCandidate:
    source: str
    reply: str
    confidence: float
    verification: str
    payload: Mapping[str, Any]
    answer_key: str = ""
    evidence_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["payload"] = dict(self.payload)
        return row


@dataclass(frozen=True)
class ReasoningPlan:
    task_form: str
    stages: tuple[str, ...]
    candidate_lanes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FAP1xGeneralReasoningCore:
    """Evidence-gated multi-lane reasoning for the public 1.x runtime.

    The core does not treat an unresolved forced choice as knowledge. It builds
    several independent candidates, ranks verified results first, exposes
    disagreements, and keeps hypotheses explicitly provisional.
    """

    VERIFIED = {
        "verified_arithmetic",
        "deterministic_physics",
        "rule_verified",
        "derivation_verified",
        "local_fact",
    }
    SUPPORTED = {
        "option_conditioned_science",
    }

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.mcq_parser = StructuredMCQParser()
        self.mcq_base = StructuredMCQReasoner()
        self.algebra = GenericLinearEquationSolver()
        self.science = OptionConditionedScientificReasoner(self.mcq_base)
        self.physics = ExpandedPhysicsSolver()
        self.factual = FactualQAOrgan()
        self.rules = GenericRuleReasoner(self.root)
        self.derivation = GenericDerivationEngine(self.root)
        self.hypotheses = HypothesisEngine(self.root)
        self.decomposer = ProblemDecomposer()
        self.verifier = IndependentCandidateVerifier(self.root)
        self.calibrator = ConfidenceCalibrator()
        self.retrieval = GroundedRetrievalReasoner(self.root)
        self.search_controller = AdaptiveSearchController()

    def plan(self, text: str) -> ReasoningPlan:
        query = str(text or "").strip()
        task = self.mcq_parser.parse(query)
        if task is not None:
            return ReasoningPlan(
                task_form="multiple_choice",
                stages=(
                    "parse_contract",
                    "generate_independent_candidates",
                    "verify_deterministic_candidates",
                    "compare_candidate_answers",
                    "select_or_fail_closed",
                ),
                candidate_lanes=(
                    "generic_linear_equation",
                    "deterministic_physics",
                    "verified_arithmetic",
                    "option_conditioned_science",
                ),
            )
        if HYPOTHESIS_CUES.search(query):
            return ReasoningPlan(
                task_form="hypothesis",
                stages=(
                    "retrieve_context",
                    "generate_competing_hypotheses",
                    "attach_predictions",
                    "attach_falsifiers",
                    "keep_provisional",
                ),
                candidate_lanes=("hypothesis_engine",),
            )
        if re.search(r"(導出|証明|示して|導いて|derive|proof|prove)", query, re.I):
            return ReasoningPlan(
                task_form="derivation",
                stages=(
                    "retrieve_derivation",
                    "symbolic_normalize",
                    "derive_target",
                    "countercheck",
                ),
                candidate_lanes=("generic_derivation", "rule_reasoner"),
            )
        return ReasoningPlan(
            task_form="open",
            stages=(
                "generate_candidates",
                "check_grounding",
                "rank_by_verification",
                "fail_closed_if_unresolved",
            ),
            candidate_lanes=("factual_qa", "rule_reasoner", "grounded_retrieval"),
        )

    def probe(self, text: str) -> float:
        query = str(text or "").strip()
        if not query:
            return 0.0
        if self.mcq_parser.parse(query) is not None:
            return 0.99
        if HYPOTHESIS_CUES.search(query):
            return 0.88
        if re.search(r"(導出|証明|示して|導いて|derive|proof|prove)", query, re.I):
            return 0.91
        if "=" in query and re.search(r"[A-Za-z]", query):
            return 0.94
        if self.factual.match(query) is not None:
            return 0.96
        if self.rules._resolve_relation(query) is not None:
            return 0.86
        retrieval_probe = self.retrieval.probe(query)
        if retrieval_probe > 0:
            return retrieval_probe
        return 0.0

    @staticmethod
    def _history(history: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        return [dict(row) for row in history]

    @staticmethod
    def _reply(payload: Mapping[str, Any]) -> str:
        return str(payload.get("reply") or payload.get("text") or "").strip()

    @staticmethod
    def _letter(payload: Mapping[str, Any]) -> str:
        reply = str(payload.get("reply") or "")
        match = re.search(r"(?i)Answer\s*:\s*\$?([A-D])\$?", reply)
        return match.group(1).upper() if match else ""

    def _mcq_candidates(
        self,
        text: str,
        history: list[Mapping[str, Any]],
    ) -> list[ReasoningCandidate]:
        task = self.mcq_parser.parse(text)
        if task is None:
            return []

        out: list[ReasoningCandidate] = []

        algebra = self.algebra.run(text, history)
        if algebra is not None and algebra.get("ok") and algebra.get("algebra_verified"):
            out.append(
                ReasoningCandidate(
                    source="generic_linear_equation",
                    reply=self._reply(algebra),
                    confidence=float(algebra.get("confidence", 0.0)),
                    verification="verified",
                    payload=algebra,
                    answer_key=self._letter(algebra),
                    evidence_count=1,
                )
            )

        physics = self.physics.run(task)
        if physics is not None and physics.get("ok"):
            out.append(
                ReasoningCandidate(
                    source="deterministic_physics",
                    reply=self._reply(physics),
                    confidence=float(physics.get("confidence", 0.0)),
                    verification="verified",
                    payload=physics,
                    answer_key=self._letter(physics),
                    evidence_count=1,
                )
            )

        base = self.mcq_base.run(task, history, teacher_allowed=False)
        base_source = str(base.get("decision_source") or "")
        if base_source == "verified_arithmetic":
            out.append(
                ReasoningCandidate(
                    source="verified_arithmetic",
                    reply=self._reply(base),
                    confidence=float(base.get("confidence", 0.0)),
                    verification="verified",
                    payload=base,
                    answer_key=self._letter(base),
                    evidence_count=1,
                )
            )

        scientific = self.science.run(task, history, teacher_allowed=False)
        science_source = str(scientific.get("decision_source") or "")
        if science_source == "option_conditioned_science":
            assessments = scientific.get("option_assessments") or []
            evidence_count = sum(
                len(row.get("evidence") or []) + len(row.get("contradictions") or [])
                for row in assessments
                if isinstance(row, Mapping)
            )
            out.append(
                ReasoningCandidate(
                    source="option_conditioned_science",
                    reply=self._reply(scientific),
                    confidence=float(scientific.get("confidence", 0.0)),
                    verification="supported",
                    payload=scientific,
                    answer_key=self._letter(scientific),
                    evidence_count=evidence_count,
                )
            )

        # Deliberately exclude unresolved_content_tiebreak. A content hash is a
        # deterministic fallback, not evidence that the answer is correct.
        return out

    def _open_candidates(
        self,
        text: str,
        history: list[Mapping[str, Any]],
    ) -> list[ReasoningCandidate]:
        out: list[ReasoningCandidate] = []

        algebra = self.algebra.run(text, history)
        if algebra is not None and algebra.get("ok") and algebra.get("algebra_verified"):
            out.append(
                ReasoningCandidate(
                    source="generic_linear_equation",
                    reply=self._reply(algebra),
                    confidence=float(algebra.get("confidence", 0.0)),
                    verification="verified",
                    payload=algebra,
                    evidence_count=1,
                )
            )

        factual = self.factual.run(text)
        if factual is not None and factual.get("ok"):
            out.append(
                ReasoningCandidate(
                    source="local_fact",
                    reply=self._reply(factual),
                    confidence=float(factual.get("confidence", 0.0)),
                    verification="verified",
                    payload=factual,
                    evidence_count=1,
                )
            )

        rule = self.rules.run(text, history)
        if rule is not None and rule.get("ok") and rule.get("rule_verified"):
            evidence = rule.get("evidence_ids") or []
            out.append(
                ReasoningCandidate(
                    source="rule_verified",
                    reply=self._reply(rule),
                    confidence=float(rule.get("confidence", 0.0)),
                    verification="verified",
                    payload=rule,
                    evidence_count=len(evidence),
                )
            )

        retrieval = self.retrieval.run(text, history)
        if retrieval is not None and retrieval.get("ok") and not retrieval.get("needs_live_retrieval"):
            evidence = retrieval.get("evidence_ids") or []
            out.append(
                ReasoningCandidate(
                    source="grounded_retrieval",
                    reply=self._reply(retrieval),
                    confidence=float(retrieval.get("confidence", 0.0)),
                    verification="supported",
                    payload=retrieval,
                    evidence_count=len(evidence),
                )
            )

        derivation = self.derivation.run(text, history)
        if (
            derivation is not None
            and derivation.get("ok")
            and derivation.get("derivation_verified")
        ):
            evidence = derivation.get("evidence_ids") or []
            out.append(
                ReasoningCandidate(
                    source="derivation_verified",
                    reply=self._reply(derivation),
                    confidence=float(derivation.get("confidence", 0.0)),
                    verification="verified",
                    payload=derivation,
                    evidence_count=len(evidence),
                )
            )

        hypothesis = self.hypotheses.run(text, history)
        if hypothesis is not None and hypothesis.get("ok"):
            hypotheses = hypothesis.get("hypotheses") or []
            out.append(
                ReasoningCandidate(
                    source="hypothesis_provisional",
                    reply=self._reply(hypothesis),
                    confidence=float(hypothesis.get("confidence", 0.0)),
                    verification="provisional",
                    payload=hypothesis,
                    evidence_count=sum(
                        len(row.get("evidence_ids") or [])
                        for row in hypotheses
                        if isinstance(row, Mapping)
                    ),
                )
            )

        return out

    def _verify_candidates(
        self,
        query: str,
        history: list[Mapping[str, Any]],
        candidates: list[ReasoningCandidate],
    ) -> list[ReasoningCandidate]:
        verified_rows: list[ReasoningCandidate] = []
        for candidate in candidates:
            report = self.verifier.verify(
                candidate.source,
                query,
                history,
                candidate.payload,
            )
            payload = dict(candidate.payload)
            payload["independent_verification"] = report.to_dict()

            verification = candidate.verification
            confidence = candidate.confidence
            if report.status == "failed":
                verification = "rejected"
                confidence = min(confidence, 0.10)
            elif report.status == "passed":
                if candidate.verification == "verified":
                    verification = "verified"
                    confidence = min(0.995, max(confidence, report.score))
                elif candidate.verification == "supported":
                    verification = "supported"
                    confidence = min(0.95, max(confidence, report.score))
            elif candidate.verification == "verified":
                # A generator may claim verification, but if the independent
                # verifier cannot reproduce it we conservatively downgrade it.
                verification = "supported"
                confidence = min(confidence, 0.70)

            verified_rows.append(
                ReasoningCandidate(
                    source=candidate.source,
                    reply=candidate.reply,
                    confidence=confidence,
                    verification=verification,
                    payload=payload,
                    answer_key=candidate.answer_key,
                    evidence_count=candidate.evidence_count,
                )
            )
        return verified_rows

    def _repeat_verified_checks(
        self,
        query: str,
        history: list[Mapping[str, Any]],
        candidates: list[ReasoningCandidate],
    ) -> list[ReasoningCandidate]:
        verifier = IndependentCandidateVerifier(self.root)
        out: list[ReasoningCandidate] = []
        for candidate in candidates:
            if candidate.verification != "verified":
                out.append(candidate)
                continue
            report = verifier.verify(
                candidate.source,
                query,
                history,
                candidate.payload,
            )
            payload = dict(candidate.payload)
            payload["repeat_independent_verification"] = report.to_dict()
            if report.status != "passed":
                out.append(
                    ReasoningCandidate(
                        source=candidate.source,
                        reply=candidate.reply,
                        confidence=min(candidate.confidence, 0.20),
                        verification="rejected",
                        payload=payload,
                        answer_key=candidate.answer_key,
                        evidence_count=candidate.evidence_count,
                    )
                )
                continue
            out.append(
                ReasoningCandidate(
                    source=candidate.source,
                    reply=candidate.reply,
                    confidence=min(0.995, max(candidate.confidence, report.score)),
                    verification="verified",
                    payload=payload,
                    answer_key=candidate.answer_key,
                    evidence_count=candidate.evidence_count,
                )
            )
        return out

    def _calibrate_candidates(
        self,
        candidates: list[ReasoningCandidate],
        *,
        repeated_verification: bool,
        disagreement: bool,
    ) -> list[ReasoningCandidate]:
        out: list[ReasoningCandidate] = []
        for candidate in candidates:
            payload = dict(candidate.payload)
            report = payload.get(
                "repeat_independent_verification"
                if repeated_verification
                else "independent_verification"
            )
            if not isinstance(report, Mapping):
                report = payload.get("independent_verification")
            verifier_score = (
                float(report.get("score", 0.0))
                if isinstance(report, Mapping)
                else 0.0
            )
            calibrated = self.calibrator.calibrate(
                verification=candidate.verification,
                generator_confidence=candidate.confidence,
                verifier_score=verifier_score,
                evidence_count=candidate.evidence_count,
                repeated_verification=repeated_verification,
                disagreement=disagreement,
            )
            payload["confidence_calibration"] = calibrated.to_dict()
            out.append(
                ReasoningCandidate(
                    source=candidate.source,
                    reply=candidate.reply,
                    confidence=calibrated.confidence,
                    verification=candidate.verification,
                    payload=payload,
                    answer_key=candidate.answer_key,
                    evidence_count=candidate.evidence_count,
                )
            )
        return out

    @staticmethod
    def _rank(candidate: ReasoningCandidate) -> tuple[int, float, int, str]:
        tier = {"verified": 3, "supported": 2, "provisional": 1}.get(
            candidate.verification,
            0,
        )
        return (
            tier,
            float(candidate.confidence),
            int(candidate.evidence_count),
            candidate.source,
        )

    @staticmethod
    def _disagreement(candidates: list[ReasoningCandidate]) -> bool:
        answers = {
            candidate.answer_key
            for candidate in candidates
            if candidate.answer_key and candidate.verification in {"verified", "supported"}
        }
        return len(answers) > 1

    def solve(
        self,
        text: str,
        history: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] = (),
    ) -> Mapping[str, Any] | None:
        query = str(text or "").strip()
        if not query:
            return None

        plan = self.plan(query)
        decomposition = self.decomposer.decompose(query)
        rows = self._history(history)
        if plan.task_form == "multiple_choice":
            candidates = self._mcq_candidates(query, rows)
        else:
            candidates = self._open_candidates(query, rows)

        candidates = self._verify_candidates(query, rows, candidates)
        active_for_policy = [x for x in candidates if x.verification != "rejected"]
        first_disagreement = self._disagreement(active_for_policy)
        search_policy = self.search_controller.policy(
            decomposition,
            disagreement=first_disagreement,
            candidate_verifications=(x.verification for x in candidates),
        )
        verification_rounds = 1
        if search_policy.repeat_independent_verification and active_for_policy:
            candidates = self._repeat_verified_checks(query, rows, candidates)
            verification_rounds = 2

        if not candidates or all(x.verification == "rejected" for x in candidates):
            if plan.task_form == "multiple_choice":
                return {
                    "ok": True,
                    "text": "この選択問題は、現在のローカル根拠と検証器では正答を検証できません。推測で選択肢を返しません。",
                    "reply": "この選択問題は、現在のローカル根拠と検証器では正答を検証できません。推測で選択肢を返しません。",
                    "confidence": 0.0,
                    "verification_state": "unresolved",
                    "needs_verification": True,
                    "reasoning_source": "fail_closed",
                    "reasoning_plan": plan.to_dict(),
                    "problem_decomposition": decomposition.to_dict(),
                    "verification_rounds": verification_rounds,
                    "adaptive_search_policy": search_policy.to_dict(),
                    "candidate_count": 0,
                    "candidate_disagreement": False,
                    "alternatives": [],
                    "reasoning_trace": [
                        "problem_decomposition",
                        "candidate_generation",
                        "independent_verification",
                        *(
                            ["repeat_independent_verification"]
                            if verification_rounds > 1 else []
                        ),
                        "no_supported_candidate",
                        "fail_closed_without_forced_choice",
                    ],
                }
            return None

        candidates = [x for x in candidates if x.verification != "rejected"]
        disagreement = self._disagreement(candidates)
        candidates = self._calibrate_candidates(
            candidates,
            repeated_verification=verification_rounds > 1,
            disagreement=disagreement,
        )
        candidates.sort(key=self._rank, reverse=True)
        verified = [x for x in candidates if x.verification == "verified"]
        supported = [x for x in candidates if x.verification == "supported"]
        provisional = [x for x in candidates if x.verification == "provisional"]

        selected: ReasoningCandidate | None = None
        if plan.task_form == "hypothesis" and provisional and search_policy.allow_provisional:
            # For an explicit hypothesis request, a clearly-labelled
            # falsifiable hypothesis is more appropriate than an extractive
            # background passage. Verified direct results still win when the
            # task is not asking for alternatives.
            selected = provisional[0]
        elif verified:
            verified_answers = {x.answer_key for x in verified if x.answer_key}
            if len(verified_answers) <= 1 and not disagreement:
                selected = verified[0]
        elif supported and not disagreement and search_policy.allow_supported:
            selected = supported[0]

        if selected is None:
            return {
                "ok": False,
                "text": "",
                "reply": "",
                "confidence": 0.0,
                "verification_state": "unresolved",
                "reasoning_plan": plan.to_dict(),
                "problem_decomposition": decomposition.to_dict(),
                "verification_rounds": verification_rounds,
                "adaptive_search_policy": search_policy.to_dict(),
                "candidate_count": len(candidates),
                "candidate_disagreement": disagreement,
                "candidates": [x.to_dict() for x in candidates[:8]],
                "reasoning_trace": [
                    "problem_decomposition",
                    "candidate_generation",
                    "independent_verification",
                    *(
                        ["repeat_independent_verification"]
                        if verification_rounds > 1 else []
                    ),
                    "verification_gate",
                    "disagreement_check",
                    "fail_closed",
                ],
            }

        return {
            "ok": True,
            "text": selected.reply,
            "reply": selected.reply,
            "confidence": selected.confidence,
            "verification_state": selected.verification,
            "reasoning_source": selected.source,
            "reasoning_plan": plan.to_dict(),
            "problem_decomposition": decomposition.to_dict(),
            "verification_rounds": verification_rounds,
            "adaptive_search_policy": search_policy.to_dict(),
            "candidate_count": len(candidates),
            "candidate_disagreement": disagreement,
            "alternatives": [
                x.to_dict()
                for x in candidates
                if x is not selected
            ][:6],
            "reasoning_trace": [
                "problem_decomposition",
                "candidate_generation",
                "independent_verification",
                *(
                    ["repeat_independent_verification"]
                    if verification_rounds > 1 else []
                ),
                "verification_gate",
                "disagreement_check",
                f"selected:{selected.source}",
            ],
            "selected_payload": dict(selected.payload),
        }
