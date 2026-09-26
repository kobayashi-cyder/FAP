from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class OrganRoute:
    organ_id: str
    score: float
    similarity: float
    active_count: int


class LazyOrganPool(Generic[T]):
    """Instantiate an organ only on first use, then reuse it for the process lifetime."""

    def __init__(self):
        self._factories: dict[str, Callable[[], T]] = {}
        self._instances: dict[str, T] = {}
        self.load_count = 0

    def register(self, organ_id: str, factory: Callable[[], T]) -> None:
        if organ_id in self._factories:
            raise ValueError(f"duplicate organ factory: {organ_id}")
        self._factories[organ_id] = factory

    def get(self, organ_id: str) -> T:
        if organ_id not in self._instances:
            factory = self._factories.get(organ_id)
            if factory is None:
                raise KeyError(organ_id)
            self._instances[organ_id] = factory()
            self.load_count += 1
        return self._instances[organ_id]

    def loaded(self) -> tuple[str, ...]:
        return tuple(sorted(self._instances))

    def is_loaded(self, organ_id: str) -> bool:
        return organ_id in self._instances


class SparseOrganRouter:
    """V82 verifier-first sparse routing reused for current V87 organs."""

    def __init__(self):
        from fap_adaptive_circuits.adaptive import AdaptiveCircuitController

        self.controller = AdaptiveCircuitController(
            top_k=1,
            memory_capacity=8,
            activation_threshold=0.18,
        )
        specs = (
            (
                "scene",
                (
                    "画像", "生成", "描画", "scene",
                    "人", "人物", "犬", "鳥", "馬", "車", "house", "landscape",
                ),
                0.12,
            ),
            (
                "cat_morphology",
                (
                    "画像", "生成", "猫", "三毛", "八割れ", "ハチワレ",
                    "キジトラ", "サバトラ", "茶トラ", "サビ",
                    "calico", "hachiware", "tabby", "tortoiseshell",
                ),
                0.17,
            ),
            (
                "scientific_dna",
                (
                    "画像", "生成", "DNA", "dna", "塩基対", "二重らせん",
                    "B-DNA", "A-DNA", "Z-DNA", "sequence",
                ),
                0.18,
            ),
        )
        for organ_id, tags, priority in specs:
            self.controller.add_circuit(
                organ_id,
                tags=tags,
                base_priority=priority,
                parameters={"v87_37_organ": 1.0},
            )
            self.controller.certify(
                organ_id,
                evidence_id=f"v87.37-organ-cert:{organ_id}",
                benchmark_score=1.0,
                static_checks=(True,),
                deterministic=True,
            )
            self.controller.registry.get(organ_id).stage = "consolidated"

    def route(self, text: str) -> OrganRoute:
        task = "画像 生成 " + str(text or "").strip()
        decision = self.controller.route(task, top_k=1)
        if not decision.selected:
            return OrganRoute("scene", 0.0, 0.0, 1)
        choice = decision.selected[0]
        return OrganRoute(
            choice.circuit_id,
            float(choice.score),
            float(choice.similarity),
            len(decision.selected),
        )
