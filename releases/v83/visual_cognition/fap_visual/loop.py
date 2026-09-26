from __future__ import annotations

from dataclasses import dataclass

from .language import NaturalLanguageVisualPlanner
from .render import RasterFrame, RendererPort, SmallRasterRenderer
from .review import LocalVisualRepairer, VisualDifference, VisualDiffer
from .vision import PrimitiveVision, VisionPort
from .visual_ir import VisualIR


@dataclass(frozen=True)
class VisualIteration:
    index: int
    draft: VisualIR
    observed: VisualIR
    diffs: tuple[VisualDifference, ...]


@dataclass(frozen=True)
class VisualLoopResult:
    target: VisualIR
    final_ir: VisualIR
    frame: RasterFrame
    observed: VisualIR
    verified: bool
    iterations: tuple[VisualIteration, ...]


class VisualCognitiveLoop:
    """Shared-state see -> imagine -> draw -> review -> repair loop."""

    def __init__(
        self,
        *,
        planner: NaturalLanguageVisualPlanner | None = None,
        renderer: RendererPort | None = None,
        vision: VisionPort | None = None,
        differ: VisualDiffer | None = None,
        repairer: LocalVisualRepairer | None = None,
    ):
        self.planner = planner or NaturalLanguageVisualPlanner()
        self.renderer = renderer or SmallRasterRenderer()
        # PrimitiveVision is the bootstrap default only. Production injects existing VisionPort.
        self.vision = vision or PrimitiveVision()
        self.differ = differ or VisualDiffer()
        self.repairer = repairer or LocalVisualRepairer()

    def run_text(self, text: str, *, max_repairs: int = 3) -> VisualLoopResult:
        return self.run(self.planner.plan(text), max_repairs=max_repairs)

    def run(
        self,
        target: VisualIR,
        *,
        draft: VisualIR | None = None,
        max_repairs: int = 3,
    ) -> VisualLoopResult:
        target.validate()
        current = draft or target
        current.validate()
        history: list[VisualIteration] = []

        # Every candidate, including the initial one and every repaired one,
        # must be rendered and returned through Vision before it can be accepted.
        for index in range(max(0, int(max_repairs)) + 1):
            frame = self.renderer.render(current)
            observed = self.vision.observe(frame)
            diffs = self.differ.compare(target, observed)
            history.append(VisualIteration(index, current, observed, diffs))
            if not diffs:
                return VisualLoopResult(
                    target, current, frame, observed, True, tuple(history)
                )
            if index >= max_repairs:
                return VisualLoopResult(
                    target, current, frame, observed, False, tuple(history)
                )
            current = self.repairer.apply(current, target, diffs)

        raise RuntimeError("unreachable visual loop state")
