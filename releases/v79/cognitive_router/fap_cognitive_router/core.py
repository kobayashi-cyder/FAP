from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field, replace
from hashlib import sha1
from typing import Any, Callable, Deque, Dict, Iterable, Mapping, Optional, Sequence, Tuple
from pathlib import Path
import json
import re
import time


class NoRouteError(RuntimeError):
    """Raised when no registered skill can satisfy a task."""


class SkillExecutionError(RuntimeError):
    """Raised when all eligible skills fail or are rejected by the critic."""


@dataclass(frozen=True)
class TaskRequest:
    text: str
    modality: str = "text"
    required_capabilities: frozenset[str] = frozenset()
    latency_budget_ms: int = 250
    precision: str = "balanced"
    online_allowed: bool = True
    max_attempts: int = 3
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def normalized(self) -> "TaskRequest":
        text = str(self.text).strip()
        if not text:
            raise ValueError("task text is required")
        if self.latency_budget_ms < 1:
            raise ValueError("latency_budget_ms must be >= 1")
        if self.precision not in {"fast", "balanced", "high"}:
            raise ValueError("precision must be fast, balanced, or high")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        return replace(
            self,
            text=text,
            modality=str(self.modality or "text").strip().lower(),
            required_capabilities=frozenset(str(x).strip().lower() for x in self.required_capabilities if str(x).strip()),
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class SkillResult:
    ok: bool
    output: Any = None
    confidence: float = 0.0
    evidence: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        output: Any,
        *,
        confidence: float = 0.8,
        evidence: Iterable[str] = (),
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "SkillResult":
        return cls(True, output, _clamp01(confidence), tuple(evidence), dict(metadata or {}))

    @classmethod
    def failure(
        cls,
        reason: str,
        *,
        confidence: float = 0.0,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "SkillResult":
        data = dict(metadata or {})
        data.setdefault("reason", str(reason))
        return cls(False, None, _clamp01(confidence), (), data)


SkillHandler = Callable[[TaskRequest, "ExecutionContext"], SkillResult | Any]


@dataclass(frozen=True)
class SkillSpec:
    name: str
    capabilities: frozenset[str]
    handler: SkillHandler
    quality: float = 0.7
    avg_latency_ms: int = 25
    resource_cost: float = 0.2
    online: bool = False
    side_effect: bool = False
    priority: int = 0
    tags: frozenset[str] = frozenset()

    def normalized(self) -> "SkillSpec":
        name = self.name.strip()
        if not name:
            raise ValueError("skill name is required")
        caps = frozenset(str(x).strip().lower() for x in self.capabilities if str(x).strip())
        if not caps:
            raise ValueError("skill capabilities are required")
        if self.avg_latency_ms < 0:
            raise ValueError("avg_latency_ms must be >= 0")
        return replace(
            self,
            name=name,
            capabilities=caps,
            quality=_clamp01(self.quality),
            resource_cost=max(0.0, min(1.0, float(self.resource_cost))),
            tags=frozenset(str(x).strip().lower() for x in self.tags if str(x).strip()),
        )


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: Dict[str, SkillSpec] = {}

    def register(self, spec: SkillSpec, *, replace_existing: bool = False) -> SkillSpec:
        clean = spec.normalized()
        if clean.name in self._skills and not replace_existing:
            raise ValueError(f"skill already registered: {clean.name}")
        self._skills[clean.name] = clean
        return clean

    def unregister(self, name: str) -> bool:
        return self._skills.pop(name, None) is not None

    def get(self, name: str) -> Optional[SkillSpec]:
        return self._skills.get(name)

    def all(self) -> Tuple[SkillSpec, ...]:
        return tuple(sorted(self._skills.values(), key=lambda s: s.name))

    def candidates(self, required: frozenset[str], *, online_allowed: bool) -> Tuple[SkillSpec, ...]:
        out = []
        for skill in self._skills.values():
            if skill.online and not online_allowed:
                continue
            if required and not required.issubset(skill.capabilities):
                continue
            out.append(skill)
        return tuple(sorted(out, key=lambda s: s.name))


@dataclass(frozen=True)
class PlannedStep:
    text: str
    capabilities: frozenset[str]


@dataclass(frozen=True)
class TaskPlan:
    steps: Tuple[PlannedStep, ...]
    inferred_capabilities: frozenset[str]
    complexity: float


class IntentAnalyzer:
    _PATTERNS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
        ("image", ("画像", "絵", "写真", "image", "draw", "generate image", "visual")),
        ("video", ("動画", "video", "movie", "clip")),
        ("stt", ("文字起こし", "音声認識", "transcribe", "speech to text")),
        ("tts", ("読み上げ", "音声出力", "speak", "text to speech", "tts")),
        ("audio", ("音声", "audio", "voice")),
        ("android", ("android", "apk", "adb", "gradle", "スマホ", "アプリ")),
        ("code", ("コード", "実装", "バグ", "デバッグ", "python", "powershell", "関数", "repo", "github")),
        ("web", ("最新", "現在", "今日", "ニュース", "調べ", "検索", "web", "internet", "latest", "current")),
        ("memory", ("覚えて", "記憶", "前に", "以前", "remember", "memory")),
        ("calculation", ("計算", "算出", "何%", "何％", "calculate", "equation")),
        ("planning", ("計画", "手順", "設計", "ロードマップ", "plan", "architecture")),
        ("deep_reasoning", ("なぜ", "原因", "比較", "分析", "推論", "仮説", "why", "analyze", "reason")),
    )
    _CHAT = ("こんにちは", "こんばんは", "おはよう", "雑談", "hello", "hi", "thanks", "ありがとう")

    def infer(self, request: TaskRequest) -> frozenset[str]:
        text = request.text.lower()
        caps = set(request.required_capabilities)
        for cap, needles in self._PATTERNS:
            if any(n.lower() in text for n in needles):
                caps.add(cap)
        if any(n in text for n in self._CHAT) or not caps:
            caps.add("chat")
        if request.modality in {"image", "audio", "video"}:
            caps.add(request.modality)
        if request.precision == "high" and ("chat" not in caps or len(text) > 120):
            caps.add("deep_reasoning")
        return frozenset(caps)


class Planner:
    _SPLIT = re.compile(
        r"(?:[。！？?!\n]+|(?:そして|また|次に|その後|ただし|しかし|一方で|then|next|after that)[、,\s]*)",
        re.IGNORECASE,
    )

    def __init__(self, analyzer: Optional[IntentAnalyzer] = None, max_steps: int = 8) -> None:
        self.analyzer = analyzer or IntentAnalyzer()
        self.max_steps = max(1, int(max_steps))

    def plan(self, request: TaskRequest) -> TaskPlan:
        clean = request.normalized()
        parts = [x.strip(" 、,") for x in self._SPLIT.split(clean.text) if x.strip(" 、,")]
        if len(parts) == 1 and len(clean.text) > 220:
            chunks = re.split(r"(?:、|;|；)", clean.text)
            parts = [x.strip() for x in chunks if x.strip()]
        parts = parts[: self.max_steps] or [clean.text]
        steps = []
        inferred = set()
        for part in parts:
            sub = replace(clean, text=part)
            caps = self.analyzer.infer(sub)
            inferred.update(caps)
            steps.append(PlannedStep(part, caps))
        complexity = min(1.0, 0.12 * len(steps) + min(0.55, len(clean.text) / 800.0) + (0.2 if "deep_reasoning" in inferred else 0.0))
        return TaskPlan(tuple(steps), frozenset(inferred), complexity)


@dataclass(frozen=True)
class RouteCandidate:
    skill_name: str
    score: float
    reasons: Tuple[str, ...]


@dataclass(frozen=True)
class RouteDecision:
    primary: str
    fallbacks: Tuple[str, ...]
    required_capabilities: frozenset[str]
    mandatory_capabilities: frozenset[str]
    candidates: Tuple[RouteCandidate, ...]
    signature: str


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class DistillationStore:
    """Tiny online learner for route outcomes.

    It never trains a model. It promotes only stable task-signature -> skill preferences,
    keeping the mechanism cheap, inspectable and reversible.
    """

    def __init__(self, *, min_support: int = 3, min_success_rate: float = 0.8, max_signatures: int = 512) -> None:
        self.min_support = max(1, int(min_support))
        self.min_success_rate = _clamp01(min_success_rate)
        self.max_signatures = max(8, int(max_signatures))
        self._counts: Dict[str, Counter[str]] = {}
        self._success: Dict[str, Counter[str]] = {}
        self._order: Deque[str] = deque()

    @staticmethod
    def signature(request: TaskRequest, capabilities: frozenset[str]) -> str:
        tokens = re.findall(r"[a-z0-9_+\-]+|[一-龥ぁ-んァ-ンー]{2,}", request.text.lower())
        coarse = tuple(tokens[:6])
        raw = "|".join((request.modality, request.precision, ",".join(sorted(capabilities)), ",".join(coarse)))
        return sha1(raw.encode("utf-8")).hexdigest()[:16]

    def record(self, signature: str, skill_name: str, success: bool) -> None:
        if signature not in self._counts:
            self._counts[signature] = Counter()
            self._success[signature] = Counter()
            self._order.append(signature)
        self._counts[signature][skill_name] += 1
        if success:
            self._success[signature][skill_name] += 1
        while len(self._order) > self.max_signatures:
            old = self._order.popleft()
            self._counts.pop(old, None)
            self._success.pop(old, None)

    def preferred(self, signature: str) -> Optional[Tuple[str, float, int]]:
        counts = self._counts.get(signature)
        if not counts:
            return None
        eligible = []
        for skill, support in counts.items():
            if support < self.min_support:
                continue
            success = self._success[signature][skill]
            rate = success / support
            if rate >= self.min_success_rate:
                eligible.append((rate, support, skill))
        if not eligible:
            return None
        rate, support, skill = max(eligible, key=lambda x: (x[0], x[1], x[2]))
        return skill, rate, support

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "min_support": self.min_support,
            "min_success_rate": self.min_success_rate,
            "max_signatures": self.max_signatures,
            "order": list(self._order),
            "counts": {k: dict(v) for k, v in self._counts.items()},
            "success": {k: dict(v) for k, v in self._success.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DistillationStore":
        if int(data.get("version", 0)) != 1:
            raise ValueError("unsupported distillation state version")
        obj = cls(
            min_support=int(data.get("min_support", 3)),
            min_success_rate=float(data.get("min_success_rate", 0.8)),
            max_signatures=int(data.get("max_signatures", 512)),
        )
        order = [str(x) for x in data.get("order", [])]
        counts = data.get("counts", {})
        success = data.get("success", {})
        for sig in order:
            if sig not in counts:
                continue
            obj._order.append(sig)
            obj._counts[sig] = Counter({str(k): int(v) for k, v in dict(counts[sig]).items() if int(v) >= 0})
            obj._success[sig] = Counter({str(k): int(v) for k, v in dict(success.get(sig, {})).items() if int(v) >= 0})
        while len(obj._order) > obj.max_signatures:
            old = obj._order.popleft()
            obj._counts.pop(old, None)
            obj._success.pop(old, None)
        return obj

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(target)

    @classmethod
    def load(cls, path: str | Path) -> "DistillationStore":
        target = Path(path)
        return cls.from_dict(json.loads(target.read_text(encoding="utf-8")))


class RoutingPolicy:
    def __init__(self, registry: SkillRegistry, distillation: Optional[DistillationStore] = None) -> None:
        self.registry = registry
        self.distillation = distillation

    def rank(self, request: TaskRequest, desired: frozenset[str], signature: str) -> Tuple[RouteCandidate, ...]:
        # Explicit capabilities are hard constraints. Inferred capabilities are soft:
        # a planner may infer several organs for a multi-step task, and no single skill
        # should be forced to implement the entire brain.
        skills = self.registry.candidates(request.required_capabilities, online_allowed=request.online_allowed)
        if not skills:
            return ()
        preferred = self.distillation.preferred(signature) if self.distillation is not None else None
        ranked = []
        for skill in skills:
            if skill.side_effect and not bool(request.metadata.get("allow_side_effects", False)):
                continue
            coverage = len(desired & skill.capabilities) / max(1, len(desired))
            if desired and coverage <= 0.0:
                continue
            latency_fit = min(1.0, request.latency_budget_ms / max(1, skill.avg_latency_ms or 1))
            local_bonus = 1.0 if not skill.online else 0.0
            side_effect_penalty = 0.12 if skill.side_effect and not bool(request.metadata.get("allow_side_effects", False)) else 0.0
            deep_bonus = 0.0
            if request.precision == "high" and "deep_reasoning" in skill.capabilities:
                deep_bonus = 0.08
            learned_bonus = 0.0
            if preferred is not None and preferred[0] == skill.name:
                learned_bonus = min(0.12, 0.04 + 0.08 * preferred[1])

            score = (
                0.46 * coverage
                + 0.22 * skill.quality
                + 0.12 * latency_fit
                + 0.08 * (1.0 - skill.resource_cost)
                + 0.05 * local_bonus
                + 0.01 * max(-5, min(5, skill.priority))
                + deep_bonus
                + learned_bonus
                - side_effect_penalty
            )
            reasons = [
                f"coverage={coverage:.2f}",
                f"quality={skill.quality:.2f}",
                f"latency_fit={latency_fit:.2f}",
                f"resource={skill.resource_cost:.2f}",
            ]
            if local_bonus:
                reasons.append("local")
            if deep_bonus:
                reasons.append("high_precision_deep")
            if learned_bonus:
                reasons.append("distilled_preference")
            if side_effect_penalty:
                reasons.append("side_effect_penalty")
            ranked.append(RouteCandidate(skill.name, round(score, 6), tuple(reasons)))
        ranked.sort(key=lambda x: (-x.score, x.skill_name))
        return tuple(ranked)


class CognitiveRouter:
    def __init__(
        self,
        registry: SkillRegistry,
        *,
        analyzer: Optional[IntentAnalyzer] = None,
        planner: Optional[Planner] = None,
        distillation: Optional[DistillationStore] = None,
    ) -> None:
        self.registry = registry
        self.analyzer = analyzer or IntentAnalyzer()
        self.planner = planner or Planner(self.analyzer)
        self.distillation = distillation or DistillationStore()
        self.policy = RoutingPolicy(registry, self.distillation)

    def route(self, request: TaskRequest) -> Tuple[RouteDecision, TaskPlan]:
        clean = request.normalized()
        plan = self.planner.plan(clean)
        desired = frozenset(set(plan.inferred_capabilities) | set(clean.required_capabilities))
        signature = self.distillation.signature(clean, desired)
        ranked = self.policy.rank(clean, desired, signature)
        if not ranked:
            raise NoRouteError(
                f"no skill matches inferred={sorted(desired)} mandatory={sorted(clean.required_capabilities)} "
                f"online_allowed={clean.online_allowed}"
            )
        primary = ranked[0].skill_name
        fallbacks = tuple(x.skill_name for x in ranked[1 : max(1, clean.max_attempts)])
        return RouteDecision(primary, fallbacks, desired, clean.required_capabilities, ranked, signature), plan


@dataclass(frozen=True)
class MemoryEntry:
    kind: str
    text: str
    weight: float
    created_at: float


class WorkingMemory:
    def __init__(self, *, max_items: int = 64, max_chars: int = 12000) -> None:
        self.max_items = max(4, int(max_items))
        self.max_chars = max(64, int(max_chars))
        self._items: Deque[MemoryEntry] = deque()

    def add(self, kind: str, text: str, *, weight: float = 1.0) -> None:
        value = str(text)
        self._items.append(MemoryEntry(str(kind), value, float(weight), time.time()))
        self._trim()

    def _trim(self) -> None:
        while len(self._items) > self.max_items:
            self._items.popleft()
        while self._items and sum(len(x.text) for x in self._items) > self.max_chars:
            self._items.popleft()

    def recent(self, limit: int = 8) -> Tuple[MemoryEntry, ...]:
        n = max(0, int(limit))
        return tuple(list(self._items)[-n:])

    def context_text(self, limit: int = 8) -> str:
        return "\n".join(f"{x.kind}: {x.text}" for x in self.recent(limit))


@dataclass(frozen=True)
class Critique:
    accepted: bool
    confidence: float
    reasons: Tuple[str, ...]
    should_escalate: bool


class Critic:
    def __init__(self, *, min_confidence: float = 0.58) -> None:
        self.min_confidence = _clamp01(min_confidence)

    def evaluate(self, request: TaskRequest, result: SkillResult, skill: SkillSpec) -> Critique:
        reasons = []
        if not result.ok:
            reasons.append("skill_failed")
        if result.confidence < self.min_confidence:
            reasons.append("low_confidence")
        require_evidence = bool(request.metadata.get("require_evidence", False))
        if require_evidence and not result.evidence:
            reasons.append("evidence_required")
        if skill.side_effect and not bool(request.metadata.get("allow_side_effects", False)):
            reasons.append("side_effect_not_allowed")
        accepted = not reasons
        should_escalate = not accepted and bool(request.metadata.get("allow_escalation", True))
        return Critique(accepted, _clamp01(result.confidence), tuple(reasons), should_escalate)


@dataclass(frozen=True)
class ExecutionContext:
    memory: WorkingMemory
    plan: TaskPlan
    route: RouteDecision
    attempt_index: int


@dataclass(frozen=True)
class RuntimeOutcome:
    result: SkillResult
    skill_name: str
    route: RouteDecision
    plan: TaskPlan
    attempts: Tuple[str, ...]
    critiques: Tuple[Critique, ...]


class CognitiveRuntime:
    def __init__(
        self,
        router: CognitiveRouter,
        *,
        memory: Optional[WorkingMemory] = None,
        critic: Optional[Critic] = None,
    ) -> None:
        self.router = router
        self.memory = memory or WorkingMemory()
        self.critic = critic or Critic()

    def _coerce_result(self, raw: SkillResult | Any) -> SkillResult:
        if isinstance(raw, SkillResult):
            return raw
        return SkillResult.success(raw, confidence=0.7)

    def handle(self, request: TaskRequest) -> RuntimeOutcome:
        clean = request.normalized()
        route, plan = self.router.route(clean)
        self.memory.add("user", clean.text, weight=1.0)

        ordered = (route.primary,) + route.fallbacks
        # Explicit deep reasoner becomes last-resort escalation even if it was not in the
        # top fallback slice, provided it satisfies the task and online constraints.
        deep_names = [
            s.name
            for s in self.router.registry.candidates(route.mandatory_capabilities, online_allowed=clean.online_allowed)
            if "deep_reasoning" in s.capabilities and s.name not in ordered
        ]
        ordered = ordered + tuple(sorted(deep_names))

        attempts = []
        critiques = []
        last_result = SkillResult.failure("no_attempt")
        for idx, name in enumerate(ordered[: clean.max_attempts]):
            skill = self.router.registry.get(name)
            if skill is None:
                continue
            attempts.append(name)
            ctx = ExecutionContext(self.memory, plan, route, idx)
            started = time.perf_counter()
            try:
                raw = skill.handler(clean, ctx)
                result = self._coerce_result(raw)
            except Exception as exc:  # fail-closed: one skill must not kill the runtime
                result = SkillResult.failure(
                    f"{type(exc).__name__}: {exc}",
                    metadata={"exception_type": type(exc).__name__},
                )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            result = replace(
                result,
                metadata={**dict(result.metadata), "elapsed_ms": round(elapsed_ms, 3), "skill": name},
            )
            critique = self.critic.evaluate(clean, result, skill)
            critiques.append(critique)
            self.router.distillation.record(route.signature, name, critique.accepted)
            last_result = result
            if critique.accepted:
                self.memory.add("assistant", str(result.output), weight=max(0.1, result.confidence))
                self.memory.add("route", f"{route.signature}:{name}:accepted", weight=0.5)
                return RuntimeOutcome(result, name, route, plan, tuple(attempts), tuple(critiques))
            self.memory.add("route", f"{route.signature}:{name}:rejected:{','.join(critique.reasons)}", weight=0.2)
            if not critique.should_escalate:
                break

        raise SkillExecutionError(
            f"all route attempts failed/rejected; attempts={attempts}; last={last_result.metadata.get('reason', 'rejected')}"
        )


@dataclass(frozen=True)
class StepOutcome:
    index: int
    text: str
    outcome: RuntimeOutcome


@dataclass(frozen=True)
class OrchestratedOutcome:
    plan: TaskPlan
    steps: Tuple[StepOutcome, ...]
    outputs: Tuple[Any, ...]


class CognitiveOrchestrator:
    """Executes a decomposed plan with one shared bounded working memory.

    The orchestrator is intentionally conservative: it does not invent dependencies or
    mutate the world by itself. Each step is rerouted through the same registry/critic,
    so capability, online and side-effect gates remain active.
    """

    def __init__(self, runtime: CognitiveRuntime, *, max_steps: int = 8) -> None:
        self.runtime = runtime
        self.max_steps = max(1, int(max_steps))

    def handle(self, request: TaskRequest) -> OrchestratedOutcome:
        clean = request.normalized()
        plan = self.runtime.router.planner.plan(clean)
        step_outcomes = []
        outputs = []
        for idx, step in enumerate(plan.steps[: self.max_steps]):
            step_request = replace(
                clean,
                text=step.text,
                # Explicit caller requirements stay mandatory; inferred step capabilities
                # remain soft routing evidence and are recomputed by the router.
                required_capabilities=clean.required_capabilities,
            )
            outcome = self.runtime.handle(step_request)
            step_outcomes.append(StepOutcome(idx, step.text, outcome))
            outputs.append(outcome.result.output)
        return OrchestratedOutcome(plan, tuple(step_outcomes), tuple(outputs))


def make_skill(
    name: str,
    capabilities: Iterable[str],
    handler: SkillHandler,
    *,
    quality: float = 0.7,
    avg_latency_ms: int = 25,
    resource_cost: float = 0.2,
    online: bool = False,
    side_effect: bool = False,
    priority: int = 0,
    tags: Iterable[str] = (),
) -> SkillSpec:
    return SkillSpec(
        name=name,
        capabilities=frozenset(capabilities),
        handler=handler,
        quality=quality,
        avg_latency_ms=avg_latency_ms,
        resource_cost=resource_cost,
        online=online,
        side_effect=side_effect,
        priority=priority,
        tags=frozenset(tags),
    )
