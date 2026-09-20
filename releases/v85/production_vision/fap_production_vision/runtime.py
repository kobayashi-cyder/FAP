from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from fap_visual import (
    CallableVisionAdapter,
    LocalVisualRepairer,
    NaturalLanguageVisualPlanner,
    RendererPort,
    VisualCognitiveLoop,
    VisualDiffer,
    VisualIR,
    VisualLoopResult,
    VisualSkillGraph,
)
from fap_visual.render import RasterFrame


VisionCallback = Callable[[RasterFrame], Any]
VisionMapper = Callable[[Any, RasterFrame], VisualIR]


@dataclass(frozen=True)
class ProductionVisionBinding:
    """Explicit production binding; no bootstrap Vision fallback is allowed."""

    name: str
    callback: VisionCallback
    mapper: Optional[VisionMapper] = None

    def build(self) -> CallableVisionAdapter:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("production vision name is required")
        if not callable(self.callback):
            raise TypeError("production vision callback must be callable")
        if self.mapper is not None and not callable(self.mapper):
            raise TypeError("production vision mapper must be callable")
        return CallableVisionAdapter(self.callback, mapper=self.mapper)


class ProductionVisualRuntime:
    """V85 host wiring from an externally supplied Vision backend into V83.

    The runtime deliberately requires an explicit production callback. It never
    substitutes PrimitiveVision when the production binding is missing.
    """

    def __init__(
        self,
        *,
        vision_callback: VisionCallback | None = None,
        vision_mapper: VisionMapper | None = None,
        vision_name: str = "host_vision",
        planner: NaturalLanguageVisualPlanner | None = None,
        renderer: RendererPort | None = None,
        differ: VisualDiffer | None = None,
        repairer: LocalVisualRepairer | None = None,
    ):
        if vision_callback is None:
            raise ValueError(
                "production vision callback is required; "
                "PrimitiveVision fallback is disabled"
            )
        self.binding = ProductionVisionBinding(
            vision_name,
            vision_callback,
            vision_mapper,
        )
        self.vision = self.binding.build()
        self.loop = VisualCognitiveLoop(
            planner=planner,
            renderer=renderer,
            vision=self.vision,
            differ=differ,
            repairer=repairer,
        )
        self.graph = VisualSkillGraph(self.loop)

    def execute_text(
        self,
        text: str,
        *,
        max_repairs: int = 3,
    ) -> VisualLoopResult:
        return self.graph.execute_text(text, max_repairs=max_repairs)

    def execute_ir(
        self,
        target: VisualIR,
        *,
        draft: VisualIR | None = None,
        max_repairs: int = 3,
    ) -> VisualLoopResult:
        return self.graph.execute_ir(
            target,
            draft=draft,
            max_repairs=max_repairs,
        )

    def manifest(self) -> dict:
        visual = self.graph.manifest()
        return {
            "schema": "fap.production-vision.v1",
            "vision_name": self.binding.name,
            "adapter": "CallableVisionAdapter",
            "requires_external_vision": True,
            "primitive_vision_fallback": False,
            "shared_state": visual["state_space"],
            "vision_feedback_required": visual["vision_feedback_required"],
            "repair_scope": visual["repair_scope"],
        }


def build_production_visual_runtime(
    *,
    vision_callback: VisionCallback | None = None,
    vision_mapper: VisionMapper | None = None,
    vision_name: str = "host_vision",
    **kwargs,
) -> ProductionVisualRuntime:
    return ProductionVisualRuntime(
        vision_callback=vision_callback,
        vision_mapper=vision_mapper,
        vision_name=vision_name,
        **kwargs,
    )
