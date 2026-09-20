from __future__ import annotations

from dataclasses import dataclass

from .loop import VisualCognitiveLoop, VisualLoopResult
from .visual_ir import VisualIR


@dataclass(frozen=True)
class SkillNode:
    name: str
    input_state: str
    output_state: str
    active: bool = True


@dataclass(frozen=True)
class SkillEdge:
    source: str
    target: str
    relation: str


class VisualSkillGraph:
    """Skill Graph integration for the shared VisualIR cognitive loop."""

    REQUIRED_NODES = ("imagine", "draw", "see", "review", "repair", "motion")

    def __init__(self, loop: VisualCognitiveLoop | None = None):
        self.loop = loop or VisualCognitiveLoop()
        self.nodes = {
            "imagine": SkillNode("imagine", "natural_language", "VisualIR"),
            "draw": SkillNode("draw", "VisualIR", "RasterFrame"),
            "see": SkillNode("see", "RasterFrame", "VisualIR"),
            "review": SkillNode("review", "VisualIR_pair", "VisualDiff"),
            "repair": SkillNode("repair", "VisualDiff+VisualIR", "VisualIR"),
            "motion": SkillNode("motion", "VisualIR@time", "VisualIR"),
        }
        self.edges = (
            SkillEdge("imagine", "draw", "materialize"),
            SkillEdge("draw", "see", "mandatory_vision_feedback"),
            SkillEdge("see", "review", "compare_to_target"),
            SkillEdge("review", "repair", "local_patch_only"),
            SkillEdge("repair", "draw", "rerender"),
            SkillEdge("motion", "draw", "sample_state"),
        )
        self._validate()

    def _validate(self) -> None:
        missing = [name for name in self.REQUIRED_NODES if name not in self.nodes or not self.nodes[name].active]
        if missing:
            raise ValueError(f"inactive/missing visual skill nodes: {missing}")
        edge_pairs = {(e.source, e.target) for e in self.edges}
        required = {("imagine", "draw"), ("draw", "see"), ("see", "review"), ("review", "repair"), ("repair", "draw")}
        if not required.issubset(edge_pairs):
            raise ValueError("visual feedback cycle is incomplete")

    def execute_text(self, text: str, *, max_repairs: int = 3) -> VisualLoopResult:
        return self.loop.run_text(text, max_repairs=max_repairs)

    def execute_ir(self, target: VisualIR, *, draft: VisualIR | None = None, max_repairs: int = 3) -> VisualLoopResult:
        return self.loop.run(target, draft=draft, max_repairs=max_repairs)

    def sample_motion(self, ir: VisualIR, t: float) -> VisualIR:
        return ir.sample(t)

    def manifest(self) -> dict:
        return {
            "schema": "fap.skill-graph.visual.v1",
            "state_space": "VisualIR",
            "nodes": [node.__dict__.copy() for node in self.nodes.values()],
            "edges": [edge.__dict__.copy() for edge in self.edges],
            "external_diffusion_required": False,
            "vision_feedback_required": True,
            "repair_scope": "local_primitive_fields",
        }
