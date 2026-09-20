from __future__ import annotations

from typing import Any

from .skill_graph import VisualSkillGraph


class VisualAdaptiveCircuitBridge:
    """Register the verified Visual Skill Graph as a V82 sparse specialist."""

    CIRCUIT_ID = "visual_cognition"
    TAGS = (
        "visual", "vision", "image", "video",
        "視覚", "画像", "描画", "図形", "動画",
    )

    def __init__(
        self,
        graph: VisualSkillGraph,
        *,
        controller: Any,
        benchmark_score: float = 1.0,
    ):
        self.graph = graph
        self.controller = controller
        self.benchmark_score = float(benchmark_score)

    def register(self):
        registry = self.controller.registry
        if self.CIRCUIT_ID not in registry.specs:
            spec = self.controller.add_circuit(
                self.CIRCUIT_ID,
                tags=self.TAGS,
                base_priority=0.20,
                parameters={
                    "max_repairs": 3.0,
                    "vision_feedback": 1.0,
                    "local_repair": 1.0,
                },
            )
        else:
            spec = registry.get(self.CIRCUIT_ID)

        if self.controller.verifier.is_eligible(spec):
            return spec

        manifest = self.graph.manifest()
        static_checks = (
            manifest["state_space"] == "VisualIR",
            manifest["vision_feedback_required"] is True,
            manifest["repair_scope"] == "local_primitive_fields",
            manifest["external_diffusion_required"] is False,
        )
        certified = self.controller.certify(
            self.CIRCUIT_ID,
            evidence_id="v83:visual-skill-graph:bootstrap",
            benchmark_score=self.benchmark_score,
            static_checks=static_checks,
            deterministic=True,
        )
        if not certified:
            raise ValueError("visual cognition circuit failed verifier-first certification")
        return spec

    def routed(self, task: str, *, top_k: int = 2) -> bool:
        decision = self.controller.route(task, top_k=top_k)
        return self.CIRCUIT_ID in decision.circuit_ids

    def execute_if_routed(
        self,
        task: str,
        *,
        visual_instruction: str | None = None,
        max_repairs: int = 3,
        top_k: int = 2,
    ):
        decision = self.controller.route(task, top_k=top_k)
        if self.CIRCUIT_ID not in decision.circuit_ids:
            return None
        return self.graph.execute_text(
            visual_instruction or task,
            max_repairs=max_repairs,
        )
