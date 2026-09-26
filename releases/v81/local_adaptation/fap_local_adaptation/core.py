from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Callable, Optional


SCHEMA_VERSION = 1


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_+\-]+|[一-龥ぁ-んァ-ンー]{2,}", (text or "").lower())


def encode_text(text: str, dim: int = 24) -> list[float]:
    """Deterministic signed hashing encoder; compact and dependency-free."""
    dim = max(4, int(dim))
    vector = [0.0] * dim
    tokens = _tokens(text)
    if not tokens:
        return vector
    for token in tokens:
        digest = sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


def _deterministic_weight(seed: int, row: int, col: int, density: float, scale: float) -> float:
    digest = sha256(f"{seed}:{row}:{col}".encode("ascii")).digest()
    gate = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    if gate > density:
        return 0.0
    unit = int.from_bytes(digest[4:8], "big") / 0xFFFFFFFF
    return (unit * 2.0 - 1.0) * scale


class FixedReservoir:
    """Mostly fixed recurrent circuit with a tiny bounded plastic overlay."""

    def __init__(
        self,
        *,
        input_dim: int = 24,
        reservoir_dim: int = 48,
        seed: int = 80,
        recurrent_density: float = 0.10,
        leak: float = 0.55,
    ):
        self.input_dim = max(4, int(input_dim))
        self.reservoir_dim = max(8, int(reservoir_dim))
        self.seed = int(seed)
        self.leak = _clamp(leak, 0.05, 1.0)
        self.input_weights = [
            [
                _deterministic_weight(self.seed + 1, i, j, 0.32, 0.42)
                for j in range(self.input_dim)
            ]
            for i in range(self.reservoir_dim)
        ]
        self.recurrent_weights = [
            [
                _deterministic_weight(self.seed + 2, i, j, recurrent_density, 0.18)
                for j in range(self.reservoir_dim)
            ]
            for i in range(self.reservoir_dim)
        ]
        self.plastic_overlay: dict[str, float] = {}
        self.state = [0.0] * self.reservoir_dim

    def reset(self) -> None:
        self.state = [0.0] * self.reservoir_dim

    def project(self, vector: list[float], previous: Optional[list[float]] = None) -> list[float]:
        if len(vector) != self.input_dim:
            raise ValueError("input vector dimension mismatch")
        prev = list(previous) if previous is not None else list(self.state)
        if len(prev) != self.reservoir_dim:
            raise ValueError("reservoir state dimension mismatch")
        result: list[float] = []
        for i in range(self.reservoir_dim):
            total = sum(w * x for w, x in zip(self.input_weights[i], vector))
            total += sum(w * x for w, x in zip(self.recurrent_weights[i], prev))
            for key, weight in self.plastic_overlay.items():
                dst, src = (int(x) for x in key.split(":"))
                if dst == i:
                    total += weight * prev[src]
            activated = math.tanh(total)
            result.append((1.0 - self.leak) * prev[i] + self.leak * activated)
        return result

    def step(self, vector: list[float]) -> list[float]:
        self.state = self.project(vector)
        return list(self.state)

    def fixed_digest(self) -> str:
        payload = json.dumps(
            {"in": self.input_weights, "rec": self.recurrent_weights},
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(payload).hexdigest()


class PredictiveReadout:
    """Learns only the next-input prediction readout; reservoir stays fixed."""

    def __init__(self, *, input_dim: int, reservoir_dim: int, learning_rate: float = 0.08):
        self.input_dim = int(input_dim)
        self.reservoir_dim = int(reservoir_dim)
        self.learning_rate = max(0.0001, min(0.5, float(learning_rate)))
        self.weights = [
            [0.0] * self.reservoir_dim
            for _ in range(self.input_dim)
        ]

    def predict(self, state: list[float]) -> list[float]:
        if len(state) != self.reservoir_dim:
            raise ValueError("readout state dimension mismatch")
        return [
            math.tanh(sum(w * x for w, x in zip(row, state)))
            for row in self.weights
        ]

    def error(self, state: list[float], target: list[float]) -> float:
        pred = self.predict(state)
        return sum((t - p) ** 2 for t, p in zip(target, pred)) / max(1, len(target))

    def learn(self, state: list[float], target: list[float], *, verified: bool) -> float:
        before = self.error(state, target)
        if not verified:
            return before
        prediction = self.predict(state)
        for out_i, (target_value, predicted) in enumerate(zip(target, prediction)):
            delta = self.learning_rate * (target_value - predicted)
            row = self.weights[out_i]
            for state_i, activity in enumerate(state):
                row[state_i] = _clamp(row[state_i] + delta * activity, -1.5, 1.5)
        return before


class LocalHebbianOverlay:
    """Sparse local plasticity layered over the fixed recurrent circuit."""

    def __init__(self, *, learning_rate: float = 0.025, max_weight: float = 0.16, max_edges: int = 96):
        self.learning_rate = max(0.0001, min(0.25, float(learning_rate)))
        self.max_weight = max(0.01, min(0.5, float(max_weight)))
        self.max_edges = max(8, int(max_edges))

    def update(
        self,
        reservoir: FixedReservoir,
        state: list[float],
        *,
        verified: bool,
        success: bool,
        top_k: int = 8,
    ) -> int:
        if not (verified and success):
            return 0
        ranked = sorted(range(len(state)), key=lambda i: abs(state[i]), reverse=True)[:max(2, top_k)]
        changed = 0
        for dst in ranked:
            for src in ranked:
                if dst == src:
                    continue
                product = state[dst] * state[src]
                if abs(product) < 0.025:
                    continue
                key = f"{dst}:{src}"
                current = reservoir.plastic_overlay.get(key, 0.0)
                updated = _clamp(
                    current + self.learning_rate * product,
                    -self.max_weight,
                    self.max_weight,
                )
                if abs(updated) < 1e-6:
                    reservoir.plastic_overlay.pop(key, None)
                else:
                    reservoir.plastic_overlay[key] = updated
                changed += 1
        if len(reservoir.plastic_overlay) > self.max_edges:
            keep = sorted(
                reservoir.plastic_overlay.items(),
                key=lambda kv: abs(kv[1]),
                reverse=True,
            )[: self.max_edges]
            reservoir.plastic_overlay = dict(keep)
        return changed


@dataclass(frozen=True)
class Counterexample:
    evidence_id: str
    text: str
    action_tag: str
    vector: list[float]
    severity: float


class CounterexampleMemory:
    """Stores verified failure patterns and returns similarity-based avoidance penalties."""

    def __init__(self, *, input_dim: int = 24, max_records: int = 128):
        self.input_dim = int(input_dim)
        self.max_records = max(8, int(max_records))
        self.records: list[Counterexample] = []
        self.seen_evidence: set[str] = set()

    def add(
        self,
        *,
        evidence_id: str,
        text: str,
        action_tag: str,
        severity: float,
        verified: bool,
    ) -> bool:
        evidence_id = str(evidence_id).strip()
        if not evidence_id:
            raise ValueError("evidence_id is required")
        if evidence_id in self.seen_evidence:
            raise ValueError("duplicate counterexample evidence")
        if not verified:
            return False
        record = Counterexample(
            evidence_id=evidence_id,
            text=str(text),
            action_tag=str(action_tag or "generic"),
            vector=encode_text(text, self.input_dim),
            severity=_clamp(severity, 0.0, 1.0),
        )
        self.records.append(record)
        self.seen_evidence.add(evidence_id)
        if len(self.records) > self.max_records:
            removed = self.records.pop(0)
            self.seen_evidence.discard(removed.evidence_id)
        return True

    def penalty(self, text: str, action_tag: str = "generic") -> float:
        query = encode_text(text, self.input_dim)
        best = 0.0
        for record in self.records:
            sim = max(0.0, _cosine(query, record.vector))
            tag_factor = 1.0 if record.action_tag == str(action_tag or "generic") else 0.55
            best = max(best, sim * record.severity * tag_factor)
        return min(1.0, best)


@dataclass(frozen=True)
class LearningResult:
    learned: bool
    predictive_error_before: float
    predictive_error_after: float
    hebbian_edges_changed: int
    counterexample_added: bool


class LocalAdaptiveCore:
    """Verifier-gated local learner: predictive coding + reservoir + Hebb + counterexamples."""

    def __init__(
        self,
        *,
        input_dim: int = 24,
        reservoir_dim: int = 48,
        seed: int = 80,
    ):
        self.input_dim = int(input_dim)
        self.reservoir = FixedReservoir(
            input_dim=self.input_dim,
            reservoir_dim=reservoir_dim,
            seed=seed,
        )
        self.readout = PredictiveReadout(
            input_dim=self.input_dim,
            reservoir_dim=self.reservoir.reservoir_dim,
        )
        self.hebb = LocalHebbianOverlay()
        self.counterexamples = CounterexampleMemory(input_dim=self.input_dim)
        self.seen_learning_evidence: set[str] = set()
        self.last_prediction: Optional[list[float]] = None
        self.last_prediction_error: Optional[float] = None

    def passive_step(self, text: str, *, action_tag: str = "generic") -> dict:
        vector = encode_text(text, self.input_dim)
        if self.last_prediction is not None:
            self.last_prediction_error = sum(
                (target - predicted) ** 2
                for target, predicted in zip(vector, self.last_prediction)
            ) / self.input_dim
        state = self.reservoir.step(vector)
        self.last_prediction = self.readout.predict(state)
        return {
            "prediction_error": self.last_prediction_error,
            "counterexample_penalty": self.counterexamples.penalty(text, action_tag),
            "fixed_reservoir": True,
            "plastic_edges": len(self.reservoir.plastic_overlay),
        }

    def transition_error(self, source_text: str, target_text: str) -> float:
        source = encode_text(source_text, self.input_dim)
        target = encode_text(target_text, self.input_dim)
        state = self.reservoir.project(source, [0.0] * self.reservoir.reservoir_dim)
        return self.readout.error(state, target)

    def learn_transition(
        self,
        *,
        source_text: str,
        target_text: str,
        evidence_id: str,
        verified: bool,
        success: bool,
        action_tag: str = "generic",
        failure_severity: float = 1.0,
    ) -> LearningResult:
        source = encode_text(source_text, self.input_dim)
        target = encode_text(target_text, self.input_dim)
        zero = [0.0] * self.reservoir.reservoir_dim
        state = self.reservoir.project(source, zero)
        before = self.readout.error(state, target)

        if not verified:
            return LearningResult(False, before, before, 0, False)

        evidence_id = str(evidence_id).strip()
        if not evidence_id:
            raise ValueError("evidence_id is required for verified learning")
        if evidence_id in self.seen_learning_evidence:
            raise ValueError("duplicate verified learning evidence")

        self.readout.learn(state, target, verified=True)
        after = self.readout.error(state, target)
        hebbian = self.hebb.update(
            self.reservoir,
            state,
            verified=True,
            success=bool(success),
        )

        counterexample_added = False
        if not success:
            counterexample_added = self.counterexamples.add(
                evidence_id=evidence_id,
                text=source_text,
                action_tag=action_tag,
                severity=failure_severity,
                verified=True,
            )
        self.seen_learning_evidence.add(evidence_id)
        return LearningResult(True, before, after, hebbian, counterexample_added)

    def guidance(self, text: str, *, action_tag: str = "generic") -> str:
        stats = self.passive_step(text, action_tag=action_tag)
        penalty = stats["counterexample_penalty"]
        err = stats["prediction_error"]
        lines = [
            "[FAP local-adaptation guidance]",
            "fixed_reservoir=true; learning=verified_local_only",
            f"counterexample_penalty={penalty:.3f}",
            f"plastic_edges={stats['plastic_edges']}",
        ]
        if err is not None:
            lines.append(f"prediction_error={err:.4f}")
        if penalty >= 0.55:
            lines.append("avoidance_hint=similar verified failure exists; do not repeat the same action pattern blindly")
        return "\n".join(lines)

    def export_state(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "input_dim": self.input_dim,
            "reservoir_dim": self.reservoir.reservoir_dim,
            "fixed_digest": self.reservoir.fixed_digest(),
            "readout": self.readout.weights,
            "plastic_overlay": self.reservoir.plastic_overlay,
            "seen_learning_evidence": sorted(self.seen_learning_evidence),
            "counterexamples": [asdict(x) for x in self.counterexamples.records],
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        payload = self.export_state()
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        envelope = {
            "payload": payload,
            "sha256": sha256(body.encode("utf-8")).hexdigest(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def load(self, path: str | Path) -> None:
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("invalid local adaptation state")
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if sha256(body.encode("utf-8")).hexdigest() != envelope.get("sha256"):
            raise ValueError("local adaptation state digest mismatch")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported local adaptation schema")
        if payload.get("input_dim") != self.input_dim:
            raise ValueError("local adaptation input dimension mismatch")
        if payload.get("reservoir_dim") != self.reservoir.reservoir_dim:
            raise ValueError("local adaptation reservoir dimension mismatch")
        if payload.get("fixed_digest") != self.reservoir.fixed_digest():
            raise ValueError("fixed reservoir digest mismatch")

        readout = payload.get("readout")
        if not isinstance(readout, list) or len(readout) != self.input_dim:
            raise ValueError("invalid readout state")
        for row in readout:
            if not isinstance(row, list) or len(row) != self.reservoir.reservoir_dim:
                raise ValueError("invalid readout row")
        self.readout.weights = [
            [_clamp(float(x), -1.5, 1.5) for x in row]
            for row in readout
        ]

        overlay = payload.get("plastic_overlay", {})
        if not isinstance(overlay, dict) or len(overlay) > self.hebb.max_edges:
            raise ValueError("invalid plastic overlay")
        restored_overlay: dict[str, float] = {}
        for key, value in overlay.items():
            parts = str(key).split(":")
            if len(parts) != 2:
                raise ValueError("invalid plastic edge key")
            dst, src = (int(x) for x in parts)
            if not (0 <= dst < self.reservoir.reservoir_dim and 0 <= src < self.reservoir.reservoir_dim):
                raise ValueError("plastic edge out of range")
            restored_overlay[str(key)] = _clamp(float(value), -self.hebb.max_weight, self.hebb.max_weight)
        self.reservoir.plastic_overlay = restored_overlay

        seen_learning = payload.get("seen_learning_evidence", [])
        if not isinstance(seen_learning, list):
            raise ValueError("invalid verified learning evidence state")
        self.seen_learning_evidence = {str(x) for x in seen_learning if str(x).strip()}

        self.counterexamples.records = []
        self.counterexamples.seen_evidence = set()
        for raw in payload.get("counterexamples", []):
            self.counterexamples.add(
                evidence_id=str(raw["evidence_id"]),
                text=str(raw["text"]),
                action_tag=str(raw.get("action_tag", "generic")),
                severity=float(raw.get("severity", 1.0)),
                verified=True,
            )


class LocalAdaptiveResponder:
    """Adds local-learning diagnostics while leaving answer authority to the wrapped responder."""

    def __init__(
        self,
        base_responder: Callable[[str, str, str], str],
        *,
        core: Optional[LocalAdaptiveCore] = None,
    ):
        if not callable(base_responder):
            raise TypeError("base_responder must be callable")
        self.base_responder = base_responder
        self.core = core or LocalAdaptiveCore()

    def __call__(self, user_text: str, context: str, mode: str) -> str:
        guidance = self.core.guidance(user_text)
        augmented = "\n".join(x for x in (context.rstrip(), guidance) if x)
        result = str(self.base_responder(user_text, augmented, mode)).strip()
        if not result:
            raise ValueError("base responder returned empty text")
        return result
