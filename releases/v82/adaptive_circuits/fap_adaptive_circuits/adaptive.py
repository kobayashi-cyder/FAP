from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import math
import re
from typing import Callable, Iterable, Optional, Sequence


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _tokens(text: str) -> list[str]:
    text = (text or "").lower()
    out: list[str] = []
    out.extend(re.findall(r"[a-z0-9_+\-]+", text))
    for chunk in re.findall(r"[一-龥ぁ-んァ-ンー]{2,}", text):
        out.append(chunk)
        # Japanese has no spaces; local n-grams make sparse routing useful.
        for n in (2, 3):
            if len(chunk) >= n:
                out.extend(chunk[i:i+n] for i in range(len(chunk) - n + 1))
    return out


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / max(1, len(sa | sb))


@dataclass
class CircuitSpec:
    circuit_id: str
    tags: tuple[str, ...]
    base_priority: float = 0.20
    generation: int = 0
    parent_id: Optional[str] = None
    parameters: dict[str, float] = field(default_factory=dict)
    verified: bool = False
    stage: str = "candidate"  # candidate -> ephemeral -> shadow -> consolidated
    quarantined: bool = False
    successes: int = 0
    failures: int = 0
    attempts: int = 0
    reward_sum: float = 0.0

    @property
    def average_reward(self) -> float:
        return self.reward_sum / self.attempts if self.attempts else 0.0


@dataclass(frozen=True)
class RouteChoice:
    circuit_id: str
    score: float
    similarity: float
    memory_boost: float


@dataclass(frozen=True)
class RouteDecision:
    task: str
    selected: tuple[RouteChoice, ...]

    @property
    def circuit_ids(self) -> tuple[str, ...]:
        return tuple(x.circuit_id for x in self.selected)


@dataclass
class ActiveMemoryEntry:
    circuit_id: str
    task_tokens: tuple[str, ...]
    reward_ema: float
    success_count: int
    last_tick: int


class VerifierFirstGate:
    """Execution eligibility is granted only after verification evidence passes."""

    def __init__(self, *, certification_threshold: float = 0.75, outcome_threshold: float = 0.70):
        self.certification_threshold = float(certification_threshold)
        self.outcome_threshold = float(outcome_threshold)
        self._certified: set[str] = set()
        self._seen_evidence: set[str] = set()

    def certify(
        self,
        spec: CircuitSpec,
        *,
        evidence_id: str,
        static_checks: Sequence[bool],
        benchmark_score: float,
        deterministic: bool,
    ) -> bool:
        evidence_id = str(evidence_id).strip()
        if not evidence_id:
            raise ValueError("certification evidence_id is required")
        if evidence_id in self._seen_evidence:
            raise ValueError("duplicate verifier evidence")
        self._seen_evidence.add(evidence_id)
        passed = (
            bool(static_checks)
            and all(bool(x) for x in static_checks)
            and bool(deterministic)
            and float(benchmark_score) >= self.certification_threshold
            and not spec.quarantined
        )
        spec.verified = bool(passed)
        if passed:
            self._certified.add(spec.circuit_id)
        else:
            self._certified.discard(spec.circuit_id)
        return passed

    def revoke(self, spec: CircuitSpec) -> None:
        spec.verified = False
        self._certified.discard(spec.circuit_id)

    def is_eligible(self, spec: CircuitSpec) -> bool:
        return spec.verified and spec.circuit_id in self._certified and not spec.quarantined

    def verify_outcome(
        self,
        *,
        evidence_id: str,
        reward: float,
        success: bool,
        invariants: Sequence[bool] = (True,),
    ) -> bool:
        evidence_id = str(evidence_id).strip()
        if not evidence_id:
            raise ValueError("outcome evidence_id is required")
        if evidence_id in self._seen_evidence:
            raise ValueError("duplicate verifier evidence")
        self._seen_evidence.add(evidence_id)
        return (
            bool(success)
            and bool(invariants)
            and all(bool(x) for x in invariants)
            and float(reward) >= self.outcome_threshold
        )


class ActiveMemory:
    """Bounded success-only memory. Failed/unverified traces are never retained here."""

    def __init__(self, *, capacity: int = 32, alpha: float = 0.35):
        self.capacity = max(1, int(capacity))
        self.alpha = _clamp(alpha)
        self.entries: dict[str, ActiveMemoryEntry] = {}
        self._tick = 0

    def observe_success(self, circuit_id: str, task: str, reward: float) -> None:
        self._tick += 1
        tokens = tuple(_tokens(task))
        reward = _clamp(reward)
        prev = self.entries.get(circuit_id)
        if prev is None:
            self.entries[circuit_id] = ActiveMemoryEntry(
                circuit_id=circuit_id,
                task_tokens=tokens,
                reward_ema=reward,
                success_count=1,
                last_tick=self._tick,
            )
        else:
            prev.reward_ema = (1.0 - self.alpha) * prev.reward_ema + self.alpha * reward
            prev.success_count += 1
            prev.last_tick = self._tick
            # Keep the most recent task signature: active memory is intentionally short-lived.
            prev.task_tokens = tokens
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        while len(self.entries) > self.capacity:
            victim = min(
                self.entries.values(),
                key=lambda x: (x.reward_ema * (1.0 + 0.15 * math.log1p(x.success_count)), x.last_tick),
            )
            self.entries.pop(victim.circuit_id, None)

    def boost(self, circuit_id: str, task: str) -> float:
        entry = self.entries.get(circuit_id)
        if entry is None:
            return 0.0
        sim = _jaccard(_tokens(task), entry.task_tokens)
        frequency = min(1.0, math.log1p(entry.success_count) / math.log(8.0))
        return 0.35 * entry.reward_ema * (0.25 + 0.75 * sim) * (0.60 + 0.40 * frequency)


class CircuitRegistry:
    def __init__(self):
        self.specs: dict[str, CircuitSpec] = {}

    def add(self, spec: CircuitSpec) -> CircuitSpec:
        if spec.circuit_id in self.specs:
            raise ValueError(f"duplicate circuit: {spec.circuit_id}")
        self.specs[spec.circuit_id] = spec
        return spec

    def get(self, circuit_id: str) -> CircuitSpec:
        return self.specs[circuit_id]

    def all(self) -> list[CircuitSpec]:
        return list(self.specs.values())


class SparseRouter:
    """Runs only a small verifier-approved subset of circuits for each task."""

    STAGE_BONUS = {"candidate": 0.0, "ephemeral": 0.02, "shadow": 0.06, "consolidated": 0.10}

    def __init__(
        self,
        registry: CircuitRegistry,
        verifier: VerifierFirstGate,
        memory: ActiveMemory,
        *,
        top_k: int = 2,
    ):
        self.registry = registry
        self.verifier = verifier
        self.memory = memory
        self.top_k = max(1, int(top_k))

    def route(self, task: str, *, top_k: Optional[int] = None) -> RouteDecision:
        task_tokens = _tokens(task)
        choices: list[RouteChoice] = []
        for spec in self.registry.all():
            if not self.verifier.is_eligible(spec):
                continue
            tag_tokens = _tokens(" ".join(spec.tags))
            similarity = _jaccard(task_tokens, tag_tokens) if task_tokens and tag_tokens else 0.0
            mem = self.memory.boost(spec.circuit_id, task)
            score = (
                _clamp(spec.base_priority)
                + 0.60 * similarity
                + mem
                + self.STAGE_BONUS.get(spec.stage, 0.0)
                + min(0.05, 0.01 * spec.generation)
            )
            choices.append(RouteChoice(spec.circuit_id, round(score, 6), round(similarity, 6), round(mem, 6)))
        choices.sort(key=lambda x: (-x.score, x.circuit_id))
        limit = max(1, int(top_k or self.top_k))
        return RouteDecision(str(task), tuple(choices[:limit]))


class CircuitEvolver:
    """Deterministic bounded neuroevolution. Children are never auto-certified."""

    def __init__(self, registry: CircuitRegistry, verifier: VerifierFirstGate, *, max_generation: int = 8):
        self.registry = registry
        self.verifier = verifier
        self.max_generation = max(1, int(max_generation))

    def propose(self, parent_id: str, *, count: int = 2) -> list[CircuitSpec]:
        parent = self.registry.get(parent_id)
        if parent.stage != "consolidated" or not self.verifier.is_eligible(parent):
            return []
        if parent.generation >= self.max_generation:
            return []
        out: list[CircuitSpec] = []
        base = dict(parent.parameters or {"budget": 0.50, "specificity": 0.50, "exploration": 0.20})
        variants = (
            {"specificity": +0.07, "budget": -0.03},
            {"exploration": +0.06, "budget": +0.02},
            {"specificity": -0.04, "exploration": +0.04},
        )
        for i, delta in enumerate(variants[: max(1, min(int(count), len(variants)))]):
            params = {k: _clamp(v) for k, v in base.items()}
            for key, change in delta.items():
                params[key] = _clamp(params.get(key, 0.5) + change)
            digest = sha256(
                (parent.circuit_id + "|" + str(parent.generation + 1) + "|" + repr(sorted(params.items()))).encode("utf-8")
            ).hexdigest()[:10]
            child = CircuitSpec(
                circuit_id=f"{parent.circuit_id}.g{parent.generation + 1}.{digest}",
                tags=parent.tags,
                base_priority=max(0.0, parent.base_priority - 0.01),
                generation=parent.generation + 1,
                parent_id=parent.circuit_id,
                parameters=params,
                verified=False,
                stage="candidate",
            )
            self.registry.add(child)
            out.append(child)
        return out


class AdaptiveCircuitController:
    def __init__(self, *, top_k: int = 2, memory_capacity: int = 32):
        self.registry = CircuitRegistry()
        self.verifier = VerifierFirstGate()
        self.memory = ActiveMemory(capacity=memory_capacity)
        self.router = SparseRouter(self.registry, self.verifier, self.memory, top_k=top_k)
        self.evolver = CircuitEvolver(self.registry, self.verifier)

    def add_circuit(
        self,
        circuit_id: str,
        *,
        tags: Sequence[str],
        base_priority: float = 0.20,
        parameters: Optional[dict[str, float]] = None,
    ) -> CircuitSpec:
        return self.registry.add(CircuitSpec(
            circuit_id=str(circuit_id),
            tags=tuple(str(x) for x in tags),
            base_priority=float(base_priority),
            parameters=dict(parameters or {}),
        ))

    def certify(
        self,
        circuit_id: str,
        *,
        evidence_id: str,
        benchmark_score: float,
        static_checks: Sequence[bool] = (True,),
        deterministic: bool = True,
    ) -> bool:
        return self.verifier.certify(
            self.registry.get(circuit_id),
            evidence_id=evidence_id,
            static_checks=static_checks,
            benchmark_score=benchmark_score,
            deterministic=deterministic,
        )

    def route(self, task: str, *, top_k: Optional[int] = None) -> RouteDecision:
        return self.router.route(task, top_k=top_k)

    def observe(
        self,
        decision: RouteDecision,
        *,
        evidence_id: str,
        reward: float,
        success: bool,
        invariants: Sequence[bool] = (True,),
    ) -> bool:
        verified_success = self.verifier.verify_outcome(
            evidence_id=evidence_id,
            reward=reward,
            success=success,
            invariants=invariants,
        )
        for choice in decision.selected:
            spec = self.registry.get(choice.circuit_id)
            spec.attempts += 1
            spec.reward_sum += _clamp(reward)
            if verified_success:
                spec.successes += 1
                self.memory.observe_success(spec.circuit_id, decision.task, reward)
                if spec.successes >= 3:
                    spec.stage = "consolidated"
                elif spec.successes >= 2:
                    spec.stage = "shadow"
                else:
                    spec.stage = "ephemeral"
            else:
                spec.failures += 1
                if (spec.failures >= 3 and spec.successes == 0) or (
                    spec.attempts >= 5 and spec.average_reward < 0.45
                ):
                    spec.quarantined = True
                    self.verifier.revoke(spec)
        return verified_success

    def evolve(self, circuit_id: str, *, count: int = 2) -> list[CircuitSpec]:
        return self.evolver.propose(circuit_id, count=count)


# V79 operator circuits. Tags are deliberately small; the router stays cheap.
CREATIVITY_CIRCUIT_TAGS: dict[str, tuple[str, ...]] = {
    "reframe": ("再設計", "捉え直す", "問題設定", "目的", "reframe"),
    "analogy": ("類推", "異分野", "対応関係", "構造", "analogy"),
    "inversion": ("反転", "前提", "逆", "しない", "inversion"),
    "combination": ("結合", "組み合わせ", "記憶", "仮説", "統合", "combination"),
    "constraint_shift": ("制約", "容量", "低ram", "省メモリ", "最小", "最大", "constraint shift"),
}


class SparseCreativityAdapter:
    """Sparse runtime over V79 creativity operators with V79 verification/replay semantics."""

    def __init__(self, base_engine, *, controller: Optional[AdaptiveCircuitController] = None, top_k: int = 2):
        self.base = base_engine
        self.controller = controller or AdaptiveCircuitController(top_k=top_k)
        self.top_k = max(1, int(top_k))
        self._bootstrap_verifier_first()

    def _bootstrap_verifier_first(self) -> None:
        # Re-run V79's own mechanism benchmarks. Runtime routing is sparse; certification is allowed
        # to spend more work because it gates execution rights.
        from fap_creativity.engine import BOOTSTRAP_CHALLENGES

        benchmarks = {operator: (task, context) for operator, task, context in BOOTSTRAP_CHALLENGES}
        consolidated = set(self.base.experience_store.consolidated_operators())
        for operator, tags in CREATIVITY_CIRCUIT_TAGS.items():
            if operator not in self.controller.registry.specs:
                self.controller.add_circuit(operator, tags=tags, base_priority=0.20)
            task, context = benchmarks[operator]
            candidates = self.base.generate(task, context, count=5)
            candidate = next((c for c in candidates if c.operator == operator), None)
            passed = False
            reward = 0.0
            if candidate is not None:
                passed, reward = self.base.verify_candidate(task, candidate)
            self.controller.certify(
                operator,
                evidence_id=f"v82-bootstrap-cert:{operator}",
                benchmark_score=reward,
                static_checks=(candidate is not None, passed, callable(getattr(self.base, "_render", None))),
                deterministic=True,
            )
            if operator in consolidated:
                self.controller.registry.get(operator).stage = "consolidated"

    def _candidate_for(self, operator: str, task: str, context: str, prior_texts: list[str]):
        # Reuse V79's renderer but execute only routed operators.
        from fap_creativity.engine import CreativeCandidate, _clamp as v79_clamp, _jaccard as v79_jaccard, _tokens as v79_tokens

        full_task = (task + " " + context).strip()
        text = self.base._render(operator, task, context)
        task_tokens = v79_tokens(full_task)
        cand_tokens = v79_tokens(text)
        overlap = v79_jaccard(task_tokens, cand_tokens)
        novelty = v79_clamp(1.0 - overlap)
        utility = v79_clamp(0.55 + 0.35 * min(1.0, overlap * 2.0))
        consistency = 1.0 if task in text else 0.75
        diversity = 1.0
        if prior_texts:
            diversity = v79_clamp(1.0 - max(v79_jaccard(cand_tokens, v79_tokens(x)) for x in prior_texts))
        learned = min(1.35, self.base.experience_store.operator_weights(full_task).get(operator, 1.0))
        base = 0.30 * novelty + 0.30 * utility + 0.25 * consistency + 0.15 * diversity
        score = v79_clamp(base * learned)
        return CreativeCandidate(
            text=text,
            operator=operator,
            novelty=round(novelty, 4),
            utility=round(utility, 4),
            consistency=round(consistency, 4),
            diversity=round(diversity, 4),
            score=round(score, 4),
        )

    def generate(self, task: str, context: str = "", *, count: int = 2):
        task = str(task or "").strip()
        if not task:
            return []
        decision = self.controller.route((task + " " + context).strip(), top_k=min(self.top_k, max(1, int(count))))
        prior_texts: list[str] = []
        out = []
        for circuit_id in decision.circuit_ids:
            if circuit_id not in CREATIVITY_CIRCUIT_TAGS:
                # Mutated children are not executed until an implementation binding exists.
                continue
            cand = self._candidate_for(circuit_id, task, context, prior_texts)
            out.append(cand)
            prior_texts.append(cand.text)
        out.sort(key=lambda x: (-x.score, x.operator))
        return out

    def record_verified_result(
        self,
        *,
        task_id: str,
        task_text: str,
        candidate,
        evidence_id: str,
        reward: float,
    ):
        exp = self.base.verified_success(
            task_id=task_id,
            task_text=task_text,
            candidate=candidate,
            evidence_id=f"v79:{evidence_id}",
            reward=reward,
        )
        decision = RouteDecision(task_text, (RouteChoice(candidate.operator, candidate.score, 1.0, 0.0),))
        self.controller.observe(
            decision,
            evidence_id=f"v82:{evidence_id}",
            reward=exp.reward,
            success=exp.verified and exp.stage != "rejected",
            invariants=(exp.verified,),
        )
        return exp


class AdaptiveCreativityResponder:
    def __init__(self, base_responder: Callable[[str, str, str], str], sparse_engine: SparseCreativityAdapter):
        if not callable(base_responder):
            raise TypeError("base_responder must be callable")
        self.base_responder = base_responder
        self.sparse_engine = sparse_engine

    def __call__(self, user_text: str, context: str, mode: str) -> str:
        candidates = self.sparse_engine.generate(user_text, context, count=self.sparse_engine.top_k)
        augmented = context.rstrip()
        if candidates:
            lines = [augmented, "[FAP V82 sparse creativity guidance]", "Verifier-approved hypotheses; not facts."]
            lines.extend(f"{c.operator}: {c.text}" for c in candidates)
            lines.append(self.sparse_engine.base.recombine(candidates))
            augmented = "\n".join(x for x in lines if x)
        output = str(self.base_responder(user_text, augmented, mode)).strip()
        if not output:
            raise ValueError("base responder returned empty text")
        return output
