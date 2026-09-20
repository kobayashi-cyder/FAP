from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable, Iterable, Mapping, Optional


MODES = ("brief", "normal", "rich", "verbose")


class LearningArtifactError(RuntimeError):
    pass


@dataclass(frozen=True)
class CircuitActivation:
    name: str
    score: float
    hits: tuple[str, ...]


@dataclass(frozen=True)
class LearningStatus:
    circuits: int
    memory_items: int
    concept_nodes: int
    concept_edges: int
    source_selftest: str
    source_artifact_sha256: str


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_+\-]+|[一-龥ぁ-んァ-ンー]{2,}", (text or "").lower()))


def _unique(items: Iterable[str], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _canonical_json_digest(path: Path) -> str:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LearningArtifactError(f"learning artifact unreadable: {path.name}") from exc
    payload = json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


class TeacherLearningState:
    """Verified loader for the Gemma 4 distilled FAP state.

    Behaviour circuits are consolidated. Teacher-derived memory remains explicitly
    shadow-weighted and is never silently promoted to factual knowledge.
    """

    def __init__(self, data_dir: Optional[Path | str] = None, *, verify_integrity: bool = True):
        self.data_dir = Path(data_dir) if data_dir is not None else Path(__file__).with_name("data")
        self.provenance = self._load_json("provenance.json")
        if verify_integrity:
            self._verify_integrity()
        self.circuits = self._load_json("teacher_consolidated_circuits.json")
        self.memory = self._load_json("fap_memory.json")
        self.concepts = self._load_json("fap_concepts.json")
        self._validate()

    def _load_json(self, name: str):
        path = self.data_dir / name
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LearningArtifactError(f"learning artifact unreadable: {name}") from exc

    def _verify_integrity(self) -> None:
        files = self.provenance.get("files")
        if not isinstance(files, dict) or not files:
            raise LearningArtifactError("provenance file hashes missing")
        for name, expected in files.items():
            path = self.data_dir / name
            if not path.is_file():
                raise LearningArtifactError(f"learning artifact missing: {name}")
            digest = _canonical_json_digest(path)
            if digest != expected.get("canonical_sha256"):
                raise LearningArtifactError(f"learning artifact digest mismatch: {name}")

    def _validate(self) -> None:
        if not isinstance(self.circuits, dict) or not self.circuits:
            raise LearningArtifactError("consolidated circuits missing")
        for name, spec in self.circuits.items():
            if not isinstance(name, str) or not name:
                raise LearningArtifactError("invalid circuit name")
            if not isinstance(spec, dict) or spec.get("stage") != "consolidated":
                raise LearningArtifactError(f"circuit is not consolidated: {name}")
            for field in ("detect", "plan", "principles"):
                value = spec.get(field)
                if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                    raise LearningArtifactError(f"invalid circuit field: {name}.{field}")

        if not isinstance(self.memory, list):
            raise LearningArtifactError("memory must be a list")
        for item in self.memory:
            if not isinstance(item, dict) or item.get("source") != "teacher_shadow":
                raise LearningArtifactError("teacher memory must remain shadow-weighted")
            if not isinstance(item.get("text"), str):
                raise LearningArtifactError("teacher shadow memory text invalid")
            weight = item.get("weight")
            if not isinstance(weight, (int, float)) or not (0 <= float(weight) <= 1):
                raise LearningArtifactError("teacher shadow memory weight invalid")

        if not isinstance(self.concepts, dict):
            raise LearningArtifactError("concept graph missing")
        if not isinstance(self.concepts.get("nodes"), list) or not isinstance(self.concepts.get("edges"), list):
            raise LearningArtifactError("concept graph schema invalid")

        expected = self.provenance.get("counts", {})
        actual = self.status()
        checks = {
            "circuits": actual.circuits,
            "memory_items": actual.memory_items,
            "concept_nodes": actual.concept_nodes,
            "concept_edges": actual.concept_edges,
        }
        for key, value in checks.items():
            if key in expected and int(expected[key]) != value:
                raise LearningArtifactError(f"learning artifact count mismatch: {key}")

    def status(self) -> LearningStatus:
        source = self.provenance.get("source_artifact", {})
        return LearningStatus(
            circuits=len(getattr(self, "circuits", {})),
            memory_items=len(getattr(self, "memory", [])),
            concept_nodes=len(getattr(self, "concepts", {}).get("nodes", [])),
            concept_edges=len(getattr(self, "concepts", {}).get("edges", [])),
            source_selftest=str(source.get("source_selftest", "unknown")),
            source_artifact_sha256=str(source.get("sha256", "")),
        )


class TeacherLearningResponder:
    """Lightweight responder/context adapter backed by consolidated Teacher circuits."""

    _STRUCTURAL = {
        "conversation_repair": re.compile(r"(違う|ではなく|じゃなく|訂正|修正|というより)"),
        "uncertainty": re.compile(r"(不明|不確実|仮説|未確認|分から|可能性|断定)"),
        "constraint_aware": re.compile(r"(RAM|メモリ|速度|精度|安全|制約|条件|容量)", re.I),
        "decomposition": re.compile(r"(分解|サブゴール|段階|手順|タスク)"),
        "verification": re.compile(r"(検証|根拠|反例|矛盾|証拠)"),
        "planning": re.compile(r"(完了条件|逆算|再計画|途中失敗|計画)"),
        "debugging": re.compile(r"(エラー|例外|失敗|不具合|動か|修正|デバッグ)"),
        "context_followup": re.compile(r"(それ|これ|その|前の|続き|さっき|どうなった)"),
        "tool_use": re.compile(r"(ツール|外部|実行|フォールバック|API|コマンド)", re.I),
        "long_form": re.compile(r"(詳しく|長め|結論|理由|具体例|例外|要約|比較)"),
    }

    def __init__(self, state: Optional[TeacherLearningState] = None):
        self.state = state or TeacherLearningState()

    def status(self) -> LearningStatus:
        return self.state.status()

    def activate(self, user_text: str, context: str = "", *, limit: int = 3) -> list[CircuitActivation]:
        text = str(user_text or "").strip()
        if not text:
            return []
        normalized = _norm(text)
        scored: list[CircuitActivation] = []
        for name, spec in self.state.circuits.items():
            score = 0.0
            hits: list[str] = []
            for cue in spec.get("detect", []):
                cue_norm = _norm(cue)
                if cue_norm and cue_norm in normalized:
                    hits.append(cue)
                    score += 1.0
            structural = self._STRUCTURAL.get(name)
            if structural is not None and structural.search(text):
                score += 2.0
            if name == "context_followup" and context.strip() and structural is not None and structural.search(text):
                score += 1.0
            score *= float(spec.get("priority", 1.0))
            if score > 0:
                scored.append(CircuitActivation(name, round(score, 4), tuple(hits[:8])))
        scored.sort(key=lambda x: (-x.score, x.name))
        return scored[: max(1, int(limit))]

    def retrieve_shadow(self, user_text: str, context: str = "", *, limit: int = 3) -> list[Mapping]:
        query = _tokens(user_text + " " + context[-2000:])
        ranked: list[tuple[float, Mapping]] = []
        if not query:
            return []
        for item in self.state.memory:
            item_tokens = _tokens(item.get("text", ""))
            if not item_tokens:
                continue
            overlap = len(query & item_tokens) / max(1, len(query | item_tokens))
            score = overlap * float(item.get("weight", 0.0))
            if score > 0:
                ranked.append((score, item))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in ranked[: max(0, int(limit))]]

    def guidance(self, user_text: str, context: str = "", mode: str = "rich") -> dict:
        if mode not in MODES:
            raise ValueError("unsupported chat mode")
        activations = self.activate(user_text, context)
        memory_limit = {"brief": 0, "normal": 1, "rich": 2, "verbose": 3}[mode]
        shadow = self.retrieve_shadow(user_text, context, limit=memory_limit)

        plans: list[str] = []
        principles: list[str] = []
        for activation in activations:
            spec = self.state.circuits[activation.name]
            plans.extend(spec.get("plan", []))
            principles.extend(spec.get("principles", []))

        return {
            "active_circuits": [a.name for a in activations],
            "activations": [
                {"name": a.name, "score": a.score, "hits": list(a.hits)} for a in activations
            ],
            "plan": _unique(plans, {"brief": 2, "normal": 4, "rich": 6, "verbose": 8}[mode]),
            "principles": _unique(principles, {"brief": 1, "normal": 2, "rich": 4, "verbose": 6}[mode]),
            "teacher_shadow": [dict(x) for x in shadow],
            "mode": mode,
        }

    def augment_context(self, user_text: str, context: str = "", mode: str = "rich") -> str:
        guide = self.guidance(user_text, context, mode)
        if not guide["active_circuits"] and not guide["teacher_shadow"]:
            return context
        lines = [context.rstrip()] if context.strip() else []
        lines.append("[FAP teacher-learning guidance]")
        lines.append("active_circuits=" + ",".join(guide["active_circuits"]))
        if guide["plan"]:
            lines.append("plan=" + " -> ".join(guide["plan"]))
        if guide["principles"]:
            lines.append("principles=" + " / ".join(guide["principles"]))
        if guide["teacher_shadow"]:
            lines.append(
                "teacher_shadow_unverified="
                + " / ".join(item["text"] for item in guide["teacher_shadow"])
            )
        return "\n".join(lines)

    def respond(self, user_text: str, context: str = "", mode: str = "rich") -> str:
        guide = self.guidance(user_text, context, mode)
        active = guide["active_circuits"]
        if not active:
            return "学習済み回路に明確な一致がありません。追加の文脈または通常のFAP responderへ委譲します。"

        parts = ["適用回路: " + ", ".join(active)]
        if guide["plan"]:
            parts.append("処理: " + " → ".join(guide["plan"]))
        if mode != "brief" and guide["principles"]:
            parts.append("原則: " + " / ".join(guide["principles"]))
        if mode in {"rich", "verbose"} and guide["teacher_shadow"]:
            parts.append(
                "Teacher shadow（未検証）: "
                + " / ".join(item["text"] for item in guide["teacher_shadow"])
            )
        return "\n".join(parts)

    def wrap(self, base_responder: Callable[[str, str, str], str]) -> Callable[[str, str, str], str]:
        if not callable(base_responder):
            raise TypeError("base_responder must be callable")

        def wrapped(user_text: str, context: str, mode: str) -> str:
            augmented = self.augment_context(user_text, context, mode)
            output = str(base_responder(user_text, augmented, mode)).strip()
            if not output:
                raise ValueError("base responder returned empty text")
            return output

        return wrapped


class LearnedManagedChat:
    """Concrete integration with the latest bounded chat layer (V75)."""

    def __init__(
        self,
        *,
        base_responder: Optional[Callable[[str, str, str], str]] = None,
        **chat_kwargs,
    ):
        from fap_managed_chat import ManagedChatSession

        self.learning = TeacherLearningResponder()
        self.chat = ManagedChatSession(**chat_kwargs)
        self.responder = (
            self.learning.wrap(base_responder)
            if base_responder is not None
            else self.learning.respond
        )

    @property
    def mode(self) -> str:
        return self.chat.mode

    @property
    def turns(self):
        return self.chat.turns

    def status(self):
        return self.chat.status()

    def submit(self, text: str) -> str:
        return self.chat.submit(text, self.responder)


def build_interaction_runtime(
    *,
    base_chat_responder: Optional[Callable[[str, str, str], str]] = None,
    **runtime_kwargs,
):
    """Integrate the learned responder with V71's interaction runtime.

    Later provider/gating layers remain additive and untouched; callers may pass the
    same image/STT/TTS providers they already use in the current main stack.
    """

    from fap_runtime import InteractionRuntime

    learning = TeacherLearningResponder()
    chat_responder = (
        learning.wrap(base_chat_responder)
        if base_chat_responder is not None
        else learning.respond
    )
    return InteractionRuntime(
        lambda text: learning.respond(text, "", "rich"),
        chat_responder=chat_responder,
        **runtime_kwargs,
    )
