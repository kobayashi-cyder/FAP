from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable, Iterable, Mapping, Optional


@dataclass(frozen=True)
class CurriculumTask:
    task_id: str
    ability: str
    prompt: str
    difficulty: float
    parent_pattern_id: str = ""
    novelty: float = 0.5
    payload: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AttemptResult:
    answer: str
    evidence: Mapping[str, object] = field(default_factory=dict)
    cost: float = 0.0


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    reward: float
    reason: str
    independent: bool = True


@dataclass(frozen=True)
class SuccessPattern:
    pattern_id: str
    ability: str
    summary: str
    signature: tuple[str, ...]
    difficulty: float
    evidence_digests: tuple[str, ...]
    reward: float
    stage: str = "ephemeral"
    uses: int = 0


@dataclass
class AbilityState:
    ability: str
    attempts: int = 0
    successes: int = 0
    ema_reward: float = 0.5
    frontier: float = 0.25
    uncertainty: float = 1.0
    stagnation: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts else 0.5

    @property
    def weakness(self) -> float:
        return max(
            0.0,
            min(
                1.0,
                0.38 * (1.0 - self.success_rate)
                + 0.26 * self.uncertainty
                + 0.22 * (1.0 - self.frontier)
                + 0.14 * min(1.0, self.stagnation / 5.0),
            ),
        )


class AbilityMap:
    """Persistent map of verified capability frontiers and learning uncertainty."""

    def __init__(
        self,
        abilities: Iterable[str],
        path: Optional[str | Path] = None,
    ):
        names = list(
            dict.fromkeys(
                str(x).strip() for x in abilities if str(x).strip()
            )
        )
        if not names:
            raise ValueError("at least one ability is required")
        self.path = Path(path) if path else None
        self.states = {name: AbilityState(name) for name in names}
        if self.path and self.path.is_file():
            self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("ability map is unreadable") from exc
        if payload.get("schema") != "fap.ability-map.v1":
            raise ValueError("unsupported ability map schema")
        raw_states = payload.get("states")
        if not isinstance(raw_states, dict):
            raise ValueError("ability map states missing")
        for name, raw in raw_states.items():
            if not isinstance(name, str) or not isinstance(raw, dict):
                raise ValueError("invalid ability map state")
            attempts = max(0, int(raw.get("attempts", 0)))
            successes = max(
                0,
                min(attempts, int(raw.get("successes", 0))),
            )
            self.states[name] = AbilityState(
                ability=name,
                attempts=attempts,
                successes=successes,
                ema_reward=max(
                    0.0,
                    min(1.0, float(raw.get("ema_reward", 0.5))),
                ),
                frontier=max(
                    0.0,
                    min(1.0, float(raw.get("frontier", 0.25))),
                ),
                uncertainty=max(
                    0.08,
                    min(1.0, float(raw.get("uncertainty", 1.0))),
                ),
                stagnation=max(0, int(raw.get("stagnation", 0))),
            )

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "schema": "fap.ability-map.v1",
                    "states": {
                        name: asdict(state)
                        for name, state in sorted(self.states.items())
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def choose_focus(self) -> AbilityState:
        def priority(state: AbilityState):
            coverage_bonus = 0.20 if state.attempts == 0 else 0.0
            repeat_penalty = 0.05 * min(state.attempts, 6)
            score = (
                state.weakness
                + 0.20 * state.uncertainty
                + coverage_bonus
                - repeat_penalty
            )
            return (score, -state.frontier, state.ability)

        return max(self.states.values(), key=priority)

    def update(
        self,
        ability: str,
        difficulty: float,
        verification: VerificationResult,
    ) -> AbilityState:
        state = self.states.setdefault(ability, AbilityState(ability))
        old_frontier = state.frontier
        state.attempts += 1
        trusted_success = bool(
            verification.passed and verification.independent
        )
        reward = (
            max(0.0, min(1.0, float(verification.reward)))
            if trusted_success
            else 0.0
        )
        state.ema_reward = 0.72 * state.ema_reward + 0.28 * reward
        if trusted_success:
            state.successes += 1
            state.frontier = max(
                state.frontier,
                min(
                    1.0,
                    0.65 * state.frontier
                    + 0.35 * float(difficulty),
                ),
            )
        state.uncertainty = max(
            0.08,
            1.0 / (1.0 + 0.35 * state.attempts),
        )
        state.stagnation = (
            0
            if state.frontier > old_frontier + 1e-9
            else state.stagnation + 1
        )
        self._save()
        return state

    def snapshot(self) -> dict:
        return {
            name: {
                "ability": name,
                "attempts": state.attempts,
                "successes": state.successes,
                "success_rate": round(state.success_rate, 4),
                "ema_reward": round(state.ema_reward, 4),
                "frontier": round(state.frontier, 4),
                "uncertainty": round(state.uncertainty, 4),
                "stagnation": state.stagnation,
                "weakness": round(state.weakness, 4),
            }
            for name, state in sorted(self.states.items())
        }


class PatternStore:
    """Persists only compressed, independently verified success patterns."""

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self.patterns: dict[str, SuccessPattern] = {}
        self.evidence_seen: set[str] = set()
        if self.path and self.path.is_file():
            self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("success pattern store is unreadable") from exc
        if payload.get("schema") != "fap.self-curriculum-patterns.v1":
            raise ValueError("unsupported success pattern schema")
        for raw in payload.get("patterns", []):
            digests = tuple(raw.get("evidence_digests", []))
            pattern = SuccessPattern(
                raw["pattern_id"],
                raw["ability"],
                raw["summary"],
                tuple(raw.get("signature", [])),
                float(raw["difficulty"]),
                digests,
                float(raw["reward"]),
                str(raw.get("stage", "ephemeral")),
                int(raw.get("uses", 0)),
            )
            self.patterns[pattern.pattern_id] = pattern
            self.evidence_seen.update(digests)

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "schema": "fap.self-curriculum-patterns.v1",
                    "patterns": [
                        asdict(p) for p in self.patterns.values()
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def add(self, pattern: SuccessPattern) -> bool:
        fresh = [
            d
            for d in pattern.evidence_digests
            if d not in self.evidence_seen
        ]
        if not fresh:
            return False
        old = self.patterns.get(pattern.pattern_id)
        if old:
            digests = tuple(
                dict.fromkeys(old.evidence_digests + tuple(fresh))
            )
            reward = round(
                (
                    old.reward * len(old.evidence_digests)
                    + pattern.reward * len(fresh)
                )
                / len(digests),
                4,
            )
            difficulty = max(old.difficulty, pattern.difficulty)
            uses = old.uses
        else:
            digests = tuple(fresh)
            reward = pattern.reward
            difficulty = pattern.difficulty
            uses = pattern.uses
        stage = (
            "consolidated"
            if len(digests) >= 3
            else "shadow"
            if len(digests) >= 2
            else "ephemeral"
        )
        self.patterns[pattern.pattern_id] = SuccessPattern(
            pattern.pattern_id,
            pattern.ability,
            pattern.summary,
            pattern.signature,
            difficulty,
            digests,
            reward,
            stage,
            uses,
        )
        self.evidence_seen.update(fresh)
        self._save()
        return True

    def for_ability(
        self,
        ability: str,
        limit: int = 3,
    ) -> list[SuccessPattern]:
        rows = [
            p for p in self.patterns.values()
            if p.ability == ability
        ]
        rows.sort(
            key=lambda p: (-p.reward, -p.difficulty, p.pattern_id)
        )
        return rows[: max(0, int(limit))]


class SuccessCompressor:
    """Irreversibly keeps reusable structure, not a raw reasoning trace."""

    @staticmethod
    def _terms(text: str) -> list[str]:
        raw = re.findall(
            r"[A-Za-z0-9_+\-]+|[一-龥ぁ-んァ-ンー]{2,}",
            str(text).lower(),
        )
        return list(dict.fromkeys(raw))

    def compress(
        self,
        task: CurriculumTask,
        attempt: AttemptResult,
        verification: VerificationResult,
    ) -> SuccessPattern:
        if not verification.passed or not verification.independent:
            raise ValueError(
                "only independently verified successes may be compressed"
            )
        evidence = json.dumps(
            dict(attempt.evidence),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        challenge = json.dumps(
            {
                "task_id": task.task_id,
                "ability": task.ability,
                "prompt": task.prompt,
                "difficulty": round(float(task.difficulty), 8),
                "parent_pattern_id": task.parent_pattern_id,
                "novelty": round(float(task.novelty), 8),
                "payload": dict(task.payload),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        digest = sha256(
            (
                challenge
                + "\n"
                + attempt.answer
                + "\n"
                + evidence
            ).encode("utf-8")
        ).hexdigest()
        task_terms = self._terms(task.prompt)
        answer_terms = self._terms(attempt.answer)
        task_set = set(task_terms)
        shared = [
            x for x in answer_terms
            if x in task_set
        ][:3]
        distinctive = [
            x for x in answer_terms
            if x not in task_set
        ][:5]
        signature = tuple(
            (shared + distinctive)[:8]
        ) or (task.ability,)
        pattern_id = sha256(
            (
                task.ability
                + "|"
                + "|".join(signature)
            ).encode("utf-8")
        ).hexdigest()[:16]
        return SuccessPattern(
            pattern_id=pattern_id,
            ability=task.ability,
            summary=(
                f"{task.ability}: "
                + " -> ".join(signature[:6])
            ),
            signature=signature,
            difficulty=round(float(task.difficulty), 4),
            evidence_digests=(digest,),
            reward=round(
                max(0.0, min(1.0, verification.reward)),
                4,
            ),
        )


class CurriculumGenerator:
    """Creates a challenge just beyond the currently verified frontier."""

    def __init__(
        self,
        challenge_templates: Optional[Mapping[str, str]] = None,
        *,
        stretch: float = 0.10,
    ):
        self.templates = dict(challenge_templates or {})
        self.stretch = max(
            0.02,
            min(0.25, float(stretch)),
        )
        self.counter = 0

    def next_difficulty(self, state: AbilityState) -> float:
        return min(
            1.0,
            max(
                0.10,
                state.frontier
                + self.stretch
                * (0.75 + state.uncertainty),
            ),
        )

    def generate(
        self,
        state: AbilityState,
        patterns: list[SuccessPattern],
    ) -> CurriculumTask:
        self.counter += 1
        difficulty = self.next_difficulty(state)
        prior = (
            patterns[0].summary
            if patterns
            else "no reusable success pattern yet"
        )
        template = self.templates.get(
            state.ability,
            (
                "Solve a new {ability} task at difficulty "
                "{difficulty:.2f}; reuse prior structure only "
                "when it generalizes. Prior: {prior}"
            ),
        )
        return CurriculumTask(
            task_id=f"self:{state.ability}:{self.counter}",
            ability=state.ability,
            prompt=template.format(
                ability=state.ability,
                difficulty=difficulty,
                prior=prior,
            ),
            difficulty=round(difficulty, 4),
            parent_pattern_id=(
                patterns[0].pattern_id
                if patterns
                else ""
            ),
            novelty=round(
                1.0
                if not patterns
                else max(
                    0.25,
                    1.0 - 0.12 * len(patterns),
                ),
                4,
            ),
        )


class SelfCurriculumEngine:
    """Ability map -> challenge -> solve -> verify -> compress -> update."""

    def __init__(
        self,
        abilities: Iterable[str],
        *,
        solver: Callable[
            [CurriculumTask, list[SuccessPattern]],
            AttemptResult | str,
        ],
        verifier: Callable[
            [CurriculumTask, AttemptResult],
            VerificationResult,
        ],
        generator: Optional[CurriculumGenerator] = None,
        compressor: Optional[SuccessCompressor] = None,
        store: Optional[PatternStore] = None,
        ability_map: Optional[AbilityMap] = None,
    ):
        if not callable(solver) or not callable(verifier):
            raise TypeError("solver and verifier must be callable")
        self.ability_map = ability_map or AbilityMap(abilities)
        self.solver = solver
        self.verifier = verifier
        self.generator = generator or CurriculumGenerator()
        self.compressor = compressor or SuccessCompressor()
        self.store = store or PatternStore()
        self.history: list[dict] = []

    def step(self) -> dict:
        focus = self.ability_map.choose_focus()
        priors = self.store.for_ability(focus.ability)
        task = self.generator.generate(focus, priors)
        try:
            raw = self.solver(task, priors)
            attempt = (
                raw
                if isinstance(raw, AttemptResult)
                else AttemptResult(str(raw))
            )
        except Exception as exc:
            attempt = AttemptResult(
                "",
                {"solver_error": type(exc).__name__},
            )
            verification = VerificationResult(
                False,
                0.0,
                f"solver_error:{type(exc).__name__}",
                independent=True,
            )
        else:
            try:
                verification = self.verifier(task, attempt)
                if not isinstance(
                    verification,
                    VerificationResult,
                ):
                    raise TypeError(
                        "verifier must return VerificationResult"
                    )
            except Exception as exc:
                verification = VerificationResult(
                    False,
                    0.0,
                    f"verifier_error:{type(exc).__name__}",
                    independent=True,
                )
        stored = False
        pattern_id = ""
        if (
            verification.passed
            and verification.independent
        ):
            pattern = self.compressor.compress(
                task,
                attempt,
                verification,
            )
            stored = self.store.add(pattern)
            pattern_id = pattern.pattern_id
        self.ability_map.update(
            task.ability,
            task.difficulty,
            verification,
        )
        event = {
            "task": asdict(task),
            "verification": asdict(verification),
            "stored_success_pattern": stored,
            "pattern_id": pattern_id,
            "ability_after": (
                self.ability_map.snapshot()[task.ability]
            ),
        }
        self.history.append(event)
        return event

    def run(self, steps: int = 1) -> list[dict]:
        return [
            self.step()
            for _ in range(max(0, int(steps)))
        ]
