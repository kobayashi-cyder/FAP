from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence


_ALLOWED_STAGES = {"candidate", "testing", "shadow", "active", "rejected"}
_ALLOWED_TRANSITIONS = {
    "candidate": {"testing", "rejected"},
    "testing": {"shadow", "rejected"},
    "shadow": {"testing", "active", "rejected"},
    "active": set(),
    "rejected": set(),
}


def _normal(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _validate_simple_value(value: Any, *, depth: int = 0) -> None:
    if depth > 8:
        raise ValueError("skill value nesting is too deep")
    if value is None or isinstance(value, (bool, str, int)):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("skill value contains non-finite float")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_simple_value(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("skill value mapping keys must be strings")
            _validate_simple_value(item, depth=depth + 1)
        return
    raise TypeError("skill values must be simple data, not executable objects")


def _encoded_size(value: Any) -> int:
    _validate_simple_value(value)
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


@dataclass(frozen=True)
class SkillBinding:
    binding_id: str
    fn: Callable[[Any], Any]
    tags: tuple[str, ...]
    verified: bool = True
    deterministic: bool = True
    side_effect_free: bool = True

    def validate(self) -> None:
        if not _normal(self.binding_id):
            raise ValueError("binding_id is required")
        if not callable(self.fn):
            raise TypeError("binding fn must be callable")
        if not self.tags or not all(_normal(x) for x in self.tags):
            raise ValueError("binding tags are required")


class BindingRegistry:
    """Host-owned verified capability bindings. Invented skills only reference these IDs."""

    def __init__(self):
        self.bindings: dict[str, SkillBinding] = {}

    def register(self, binding: SkillBinding) -> SkillBinding:
        binding.validate()
        if binding.binding_id in self.bindings:
            raise ValueError(f"duplicate binding: {binding.binding_id}")
        self.bindings[binding.binding_id] = binding
        return binding

    def get(self, binding_id: str) -> SkillBinding:
        return self.bindings[binding_id]

    def is_eligible(self, binding_id: str) -> bool:
        binding = self.bindings.get(binding_id)
        return bool(
            binding
            and binding.verified
            and binding.deterministic
            and binding.side_effect_free
        )

    def find(self, tag: str, *, exclude: Iterable[str] = ()) -> SkillBinding | None:
        needle = _normal(tag)
        excluded = set(exclude)
        rows = []
        for binding in self.bindings.values():
            if binding.binding_id in excluded or not self.is_eligible(binding.binding_id):
                continue
            tags = {_normal(x) for x in binding.tags}
            if needle in tags:
                rows.append(binding)
        rows.sort(key=lambda x: x.binding_id)
        return rows[0] if rows else None


@dataclass(frozen=True)
class SkillNode:
    node_id: str
    binding_id: str


@dataclass(frozen=True)
class SkillEdge:
    source: str
    target: str


@dataclass(frozen=True)
class SkillSpec:
    skill_id: str
    name: str
    ability: str
    tags: tuple[str, ...]
    nodes: tuple[SkillNode, ...]
    edges: tuple[SkillEdge, ...]
    output_node: str

    @staticmethod
    def _payload(
        name: str,
        ability: str,
        tags: Sequence[str],
        nodes: Sequence[SkillNode],
        edges: Sequence[SkillEdge],
        output_node: str,
    ) -> dict:
        return {
            "name": str(name),
            "ability": str(ability),
            "tags": list(tags),
            "nodes": [asdict(x) for x in nodes],
            "edges": [asdict(x) for x in edges],
            "output_node": str(output_node),
        }

    @classmethod
    def create(
        cls,
        *,
        name: str,
        ability: str,
        tags: Sequence[str],
        nodes: Sequence[SkillNode],
        edges: Sequence[SkillEdge],
        output_node: str,
    ) -> "SkillSpec":
        payload = cls._payload(name, ability, tags, nodes, edges, output_node)
        digest = sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:16]
        spec = cls(
            f"skill:{digest}",
            str(name),
            str(ability),
            tuple(str(x) for x in tags),
            tuple(nodes),
            tuple(edges),
            str(output_node),
        )
        SkillGraphValidator.validate(spec)
        return spec

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            **self._payload(
                self.name,
                self.ability,
                self.tags,
                self.nodes,
                self.edges,
                self.output_node,
            ),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SkillSpec":
        expected = {
            "skill_id", "name", "ability", "tags",
            "nodes", "edges", "output_node",
        }
        if set(raw) != expected:
            raise ValueError("invalid generic skill schema")
        if not isinstance(raw["tags"], list):
            raise ValueError("generic skill tags must be a list")
        nodes_raw = raw["nodes"]
        edges_raw = raw["edges"]
        if not isinstance(nodes_raw, list) or not isinstance(edges_raw, list):
            raise ValueError("generic skill graph must contain node/edge lists")
        nodes = []
        for item in nodes_raw:
            if not isinstance(item, dict) or set(item) != {"node_id", "binding_id"}:
                raise ValueError("invalid generic skill node")
            nodes.append(SkillNode(str(item["node_id"]), str(item["binding_id"])))
        edges = []
        for item in edges_raw:
            if not isinstance(item, dict) or set(item) != {"source", "target"}:
                raise ValueError("invalid generic skill edge")
            edges.append(SkillEdge(str(item["source"]), str(item["target"])))
        spec = cls(
            str(raw["skill_id"]),
            str(raw["name"]),
            str(raw["ability"]),
            tuple(str(x) for x in raw["tags"]),
            tuple(nodes),
            tuple(edges),
            str(raw["output_node"]),
        )
        SkillGraphValidator.validate(spec)
        expected_id = cls.create(
            name=spec.name,
            ability=spec.ability,
            tags=spec.tags,
            nodes=spec.nodes,
            edges=spec.edges,
            output_node=spec.output_node,
        ).skill_id
        if spec.skill_id != expected_id:
            raise ValueError("generic skill identity digest mismatch")
        return spec


class SkillGraphValidator:
    @staticmethod
    def topological(spec: SkillSpec) -> tuple[str, ...]:
        node_ids = [node.node_id for node in spec.nodes]
        if not node_ids or len(node_ids) != len(set(node_ids)):
            raise ValueError("generic skill nodes must be unique and non-empty")
        if not _normal(spec.name) or not _normal(spec.ability):
            raise ValueError("generic skill name and ability are required")
        if not spec.tags or not all(_normal(x) for x in spec.tags):
            raise ValueError("generic skill tags are required")
        if spec.output_node not in set(node_ids):
            raise ValueError("generic skill output node is missing")
        if len(spec.nodes) > 12:
            raise ValueError("generic skill exceeds node limit")

        known = set(node_ids)
        indegree = {node_id: 0 for node_id in node_ids}
        adjacency = {node_id: [] for node_id in node_ids}
        reverse = {node_id: [] for node_id in node_ids}
        edge_pairs: set[tuple[str, str]] = set()
        for edge in spec.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError("generic skill edge references missing node")
            pair = (edge.source, edge.target)
            if edge.source == edge.target or pair in edge_pairs:
                raise ValueError("invalid or duplicate generic skill edge")
            edge_pairs.add(pair)
            indegree[edge.target] += 1
            adjacency[edge.source].append(edge.target)
            reverse[edge.target].append(edge.source)

        queue = sorted(node for node, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            for target in sorted(adjacency[current]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
                    queue.sort()
        if len(order) != len(node_ids):
            raise ValueError("generic skill graph must be acyclic")

        ancestors = {spec.output_node}
        stack = [spec.output_node]
        while stack:
            current = stack.pop()
            for parent in reverse[current]:
                if parent not in ancestors:
                    ancestors.add(parent)
                    stack.append(parent)
        if ancestors != known:
            raise ValueError("generic skill contains nodes not contributing to output")
        return tuple(order)

    @staticmethod
    def validate(spec: SkillSpec) -> None:
        SkillGraphValidator.topological(spec)
        if len({node.binding_id for node in spec.nodes if _normal(node.binding_id)}) != len(spec.nodes):
            # Reusing one binding twice is intentionally disallowed in the first
            # generic release to keep invented graphs compact and inspectable.
            raise ValueError("generic skill binding references must be unique")


@dataclass(frozen=True)
class SkillExecution:
    skill_id: str
    ok: bool
    output: Any = None
    error: str = ""
    timed_out: bool = False
    steps: int = 0


class SkillSandbox:
    """Bounded dataflow runner over host-verified bindings; no generated code/imports."""

    def __init__(
        self,
        bindings: BindingRegistry,
        *,
        max_nodes: int = 12,
        max_payload_bytes: int = 65536,
        timeout_ms: float = 50.0,
    ):
        self.bindings = bindings
        self.max_nodes = max(1, min(12, int(max_nodes)))
        self.max_payload_bytes = max(256, int(max_payload_bytes))
        self.timeout_ms = max(1.0, float(timeout_ms))

    def execute(self, spec: SkillSpec, value: Any) -> SkillExecution:
        try:
            SkillGraphValidator.validate(spec)
            if len(spec.nodes) > self.max_nodes:
                raise ValueError("generic skill exceeds sandbox node budget")
            if _encoded_size(value) > self.max_payload_bytes:
                raise ValueError("generic skill input exceeds payload budget")
            node_map = {node.node_id: node for node in spec.nodes}
            parents = {node.node_id: [] for node in spec.nodes}
            for edge in spec.edges:
                parents[edge.target].append(edge.source)
            order = SkillGraphValidator.topological(spec)
            outputs: dict[str, Any] = {}
            started = perf_counter()
            for index, node_id in enumerate(order, start=1):
                node = node_map[node_id]
                if not self.bindings.is_eligible(node.binding_id):
                    raise ValueError(f"unverified skill binding: {node.binding_id}")
                sources = sorted(parents[node_id])
                node_input = (
                    value
                    if not sources
                    else outputs[sources[0]]
                    if len(sources) == 1
                    else tuple(outputs[x] for x in sources)
                )
                _validate_simple_value(node_input)
                binding = self.bindings.get(node.binding_id)
                output = binding.fn(node_input)
                _validate_simple_value(output)
                if _encoded_size(output) > self.max_payload_bytes:
                    raise ValueError("generic skill output exceeds payload budget")
                outputs[node_id] = output
                elapsed_ms = (perf_counter() - started) * 1000.0
                if elapsed_ms > self.timeout_ms:
                    return SkillExecution(
                        spec.skill_id,
                        False,
                        error="timeout_budget_exceeded",
                        timed_out=True,
                        steps=index,
                    )
            return SkillExecution(
                spec.skill_id,
                True,
                output=outputs[spec.output_node],
                steps=len(order),
            )
        except Exception as exc:
            return SkillExecution(
                spec.skill_id,
                False,
                error=f"{type(exc).__name__}:{exc}",
            )


@dataclass(frozen=True)
class SkillTestCase:
    value: Any
    expected: Any
    boundary: bool = False
    label: str = ""


@dataclass(frozen=True)
class PromotionDecision:
    skill_id: str
    stage: str
    promoted: bool
    unit_passed: int
    unit_total: int
    shadow_successes: int
    deterministic: bool
    timeout_free: bool
    reason: str


class SkillInventor:
    """Invents declarative DAGs by composing only eligible existing bindings."""

    def __init__(self, bindings: BindingRegistry, *, max_steps: int = 6):
        self.bindings = bindings
        self.max_steps = max(1, min(12, int(max_steps)))

    def invent(
        self,
        *,
        name: str,
        ability: str,
        required_tags: Sequence[str],
    ) -> SkillSpec:
        tags = tuple(_normal(x) for x in required_tags if _normal(x))
        if not tags:
            raise ValueError("required_tags are required")
        if len(tags) > self.max_steps:
            raise ValueError("invented skill exceeds max_steps")
        selected: list[SkillBinding] = []
        used: set[str] = set()
        for tag in tags:
            binding = self.bindings.find(tag, exclude=used)
            if binding is None:
                raise ValueError(f"no verified binding for capability tag: {tag}")
            selected.append(binding)
            used.add(binding.binding_id)
        nodes = tuple(
            SkillNode(f"n{index}", binding.binding_id)
            for index, binding in enumerate(selected)
        )
        edges = tuple(
            SkillEdge(nodes[index].node_id, nodes[index + 1].node_id)
            for index in range(len(nodes) - 1)
        )
        return SkillSpec.create(
            name=name,
            ability=ability,
            tags=tuple(dict.fromkeys((ability, *tags))),
            nodes=nodes,
            edges=edges,
            output_node=nodes[-1].node_id,
        )


def validate_skill_registry_payload(
    payload: Any,
    *,
    bindings: BindingRegistry | None = None,
) -> list[dict]:
    if not isinstance(payload, dict) or set(payload) != {"schema", "records"}:
        raise ValueError("invalid generic skill registry payload")
    if payload["schema"] != "fap.generic-skill-registry.v1":
        raise ValueError("unsupported generic skill registry schema")
    records = payload["records"]
    if not isinstance(records, list):
        raise ValueError("invalid generic skill registry records")
    seen: set[str] = set()
    validated = []
    for raw in records:
        if not isinstance(raw, dict) or set(raw) != {"skill_id", "stage", "skill", "evidence"}:
            raise ValueError("invalid generic skill registry record")
        skill_id = str(raw["skill_id"])
        if skill_id in seen:
            raise ValueError("duplicate generic skill id")
        seen.add(skill_id)
        spec = SkillSpec.from_dict(raw["skill"])
        if spec.skill_id != skill_id:
            raise ValueError("generic skill record identity mismatch")
        stage = raw["stage"]
        if stage not in _ALLOWED_STAGES:
            raise ValueError("invalid generic skill stage")
        evidence = raw["evidence"]
        if not isinstance(evidence, dict):
            raise ValueError("invalid generic skill evidence")
        transitions = evidence.get("transitions")
        if (
            not isinstance(transitions, list)
            or not transitions
            or transitions[0] != "candidate"
            or transitions[-1] != stage
        ):
            raise ValueError("invalid generic skill transition history")
        previous = transitions[0]
        for current in transitions[1:]:
            if current not in _ALLOWED_TRANSITIONS.get(previous, set()):
                raise ValueError("illegal generic skill transition")
            previous = current
        if stage == "active":
            if (
                int(evidence.get("unit_total", 0)) < 3
                or int(evidence.get("unit_passed", 0)) != int(evidence.get("unit_total", 0))
                or evidence.get("boundary_passed") is not True
                or evidence.get("deterministic") is not True
                or evidence.get("timeout_free") is not True
                or int(evidence.get("shadow_successes", 0)) < 3
                or evidence.get("promotion") != "passed"
            ):
                raise ValueError("active generic skill lacks promotion evidence")
            if bindings is None:
                raise ValueError("active persisted skills require a binding registry")
            if any(not bindings.is_eligible(node.binding_id) for node in spec.nodes):
                raise ValueError("active persisted skill references ineligible binding")
        validated.append(dict(raw))
    return validated


class SkillRegistry:
    def __init__(
        self,
        path: Optional[str | Path] = None,
        *,
        bindings: BindingRegistry | None = None,
    ):
        self.path = Path(path) if path else None
        self.bindings = bindings
        self.records: dict[str, dict] = {}
        if self.path and self.path.is_file():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            for record in validate_skill_registry_payload(payload, bindings=bindings):
                self.records[record["skill_id"]] = record

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "schema": "fap.generic-skill-registry.v1",
                    "records": list(self.records.values()),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def add_candidate(self, spec: SkillSpec) -> dict:
        if spec.skill_id in self.records:
            return self.records[spec.skill_id]
        record = {
            "skill_id": spec.skill_id,
            "stage": "candidate",
            "skill": spec.to_dict(),
            "evidence": {"transitions": ["candidate"]},
        }
        self.records[spec.skill_id] = record
        self._save()
        return record

    def transition(self, skill_id: str, stage: str) -> None:
        record = self.records[skill_id]
        current = record["stage"]
        if stage not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise ValueError(f"illegal generic skill transition: {current}->{stage}")
        record["stage"] = stage
        record["evidence"].setdefault("transitions", []).append(stage)
        self._save()

    def update_evidence(self, skill_id: str, **evidence: Any) -> None:
        record = self.records[skill_id]
        record["evidence"].update(evidence)
        self._save()

    def get(self, skill_id: str) -> dict:
        return self.records[skill_id]

    def active(self) -> list[dict]:
        return [row for row in self.records.values() if row["stage"] == "active"]


class SkillPromotionLoop:
    def __init__(
        self,
        sandbox: SkillSandbox,
        registry: SkillRegistry,
    ):
        self.sandbox = sandbox
        self.registry = registry

    def evaluate(
        self,
        spec: SkillSpec,
        *,
        unit_cases: Sequence[SkillTestCase],
        shadow_cases: Sequence[SkillTestCase],
    ) -> PromotionDecision:
        record = self.registry.add_candidate(spec)
        if record["stage"] == "active":
            evidence = record["evidence"]
            return PromotionDecision(
                spec.skill_id,
                "active",
                True,
                int(evidence.get("unit_passed", 0)),
                int(evidence.get("unit_total", 0)),
                int(evidence.get("shadow_successes", 0)),
                bool(evidence.get("deterministic")),
                bool(evidence.get("timeout_free")),
                "already_active",
            )
        if record["stage"] not in {"candidate", "shadow"}:
            return PromotionDecision(
                spec.skill_id,
                record["stage"],
                False,
                0,
                len(unit_cases),
                0,
                False,
                False,
                "candidate_not_evaluable",
            )
        self.registry.transition(spec.skill_id, "testing")

        if len(unit_cases) < 3 or not any(case.boundary for case in unit_cases):
            self.registry.update_evidence(
                spec.skill_id,
                unit_total=len(unit_cases),
                unit_passed=0,
                boundary_passed=False,
                deterministic=False,
                timeout_free=False,
            )
            self.registry.transition(spec.skill_id, "rejected")
            return PromotionDecision(
                spec.skill_id,
                "rejected",
                False,
                0,
                len(unit_cases),
                0,
                False,
                False,
                "insufficient_unit_or_boundary_coverage",
            )

        passed = 0
        boundary_passed = True
        deterministic = True
        timeout_free = True
        for case in unit_cases:
            first = self.sandbox.execute(spec, case.value)
            second = self.sandbox.execute(spec, case.value)
            timeout_free = timeout_free and not first.timed_out and not second.timed_out
            same = first.ok and second.ok and first.output == second.output
            deterministic = deterministic and same
            ok = same and first.output == case.expected
            if ok:
                passed += 1
            elif case.boundary:
                boundary_passed = False

        unit_ok = (
            passed == len(unit_cases)
            and boundary_passed
            and deterministic
            and timeout_free
        )
        if not unit_ok:
            self.registry.update_evidence(
                spec.skill_id,
                unit_total=len(unit_cases),
                unit_passed=passed,
                boundary_passed=boundary_passed,
                deterministic=deterministic,
                timeout_free=timeout_free,
            )
            self.registry.transition(spec.skill_id, "rejected")
            return PromotionDecision(
                spec.skill_id,
                "rejected",
                False,
                passed,
                len(unit_cases),
                0,
                deterministic,
                timeout_free,
                "unit_verification_failed",
            )

        self.registry.transition(spec.skill_id, "shadow")
        shadow_successes = 0
        shadow_timeout_free = True
        for case in shadow_cases:
            result = self.sandbox.execute(spec, case.value)
            shadow_timeout_free = shadow_timeout_free and not result.timed_out
            if result.ok and result.output == case.expected:
                shadow_successes += 1

        timeout_free = timeout_free and shadow_timeout_free
        self.registry.update_evidence(
            spec.skill_id,
            unit_total=len(unit_cases),
            unit_passed=passed,
            boundary_passed=boundary_passed,
            deterministic=deterministic,
            timeout_free=timeout_free,
            shadow_successes=shadow_successes,
        )
        if (
            len(shadow_cases) >= 3
            and shadow_successes == len(shadow_cases)
            and timeout_free
        ):
            self.registry.update_evidence(spec.skill_id, promotion="passed")
            self.registry.transition(spec.skill_id, "active")
            return PromotionDecision(
                spec.skill_id,
                "active",
                True,
                passed,
                len(unit_cases),
                shadow_successes,
                deterministic,
                timeout_free,
                "verified_active",
            )
        return PromotionDecision(
            spec.skill_id,
            "shadow",
            False,
            passed,
            len(unit_cases),
            shadow_successes,
            deterministic,
            timeout_free,
            "shadow_evidence_incomplete",
        )


class GenericSkillGraph:
    """Runtime graph of promoted generic skill DAGs."""

    def __init__(
        self,
        sandbox: SkillSandbox,
        registry: SkillRegistry,
    ):
        self.sandbox = sandbox
        self.registry = registry

    def execute(self, skill_id: str, value: Any) -> SkillExecution:
        record = self.registry.get(skill_id)
        if record["stage"] != "active":
            raise ValueError("generic skill is not active")
        spec = SkillSpec.from_dict(record["skill"])
        return self.sandbox.execute(spec, value)

    def manifest(self) -> dict:
        return {
            "schema": "fap.skill-graph.generic.v1",
            "execution_model": "verified_binding_dag",
            "generated_code_allowed": False,
            "active_skills": [
                {
                    "skill_id": row["skill_id"],
                    "name": row["skill"]["name"],
                    "ability": row["skill"]["ability"],
                    "tags": list(row["skill"]["tags"]),
                    "nodes": list(row["skill"]["nodes"]),
                    "edges": list(row["skill"]["edges"]),
                }
                for row in sorted(
                    self.registry.active(),
                    key=lambda x: x["skill_id"],
                )
            ],
        }


class GenericSkillFactory:
    def __init__(
        self,
        bindings: BindingRegistry,
        *,
        registry_path: Optional[str | Path] = None,
        timeout_ms: float = 50.0,
    ):
        self.bindings = bindings
        self.inventor = SkillInventor(bindings)
        self.sandbox = SkillSandbox(bindings, timeout_ms=timeout_ms)
        self.registry = SkillRegistry(registry_path, bindings=bindings)
        self.promotion = SkillPromotionLoop(self.sandbox, self.registry)
        self.graph = GenericSkillGraph(self.sandbox, self.registry)

    def invent_and_promote(
        self,
        *,
        name: str,
        ability: str,
        required_tags: Sequence[str],
        unit_cases: Sequence[SkillTestCase],
        shadow_cases: Sequence[SkillTestCase],
    ) -> tuple[SkillSpec, PromotionDecision]:
        spec = self.inventor.invent(
            name=name,
            ability=ability,
            required_tags=required_tags,
        )
        decision = self.promotion.evaluate(
            spec,
            unit_cases=unit_cases,
            shadow_cases=shadow_cases,
        )
        return spec, decision
