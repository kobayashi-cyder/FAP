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
    """FAP see/imagine/draw/review loop in a shared VisualIR state space."""

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
        self.vision = vision or PrimitiveVision()
        self.differ = differ or VisualDiffer()
        self.repairer = repairer or LocalVisualRepairer()

    def run_text(self, text: str, *, max_repairs: int = 3) -> VisualLoopResult:
        target = self.planner.plan(text)
        return self.run(target, max_repairs=max_repairs)

    def run(self, target: VisualIR, *, draft: VisualIR | None = None, max_repairs: int = 3) -> VisualLoopResult:
        target.validate()
        current = draft or target
        current.validate()
        history: list[VisualIteration] = []
        frame = self.renderer.render(current)
        observed = self.vision.observe(frame)
        for idx in range(max(0, int(max_repairs)) + 1):
            if idx:
                frame = self.renderer.render(current)
                observed = self.vision.observe(frame)
            diffs = self.differ.compare(target, observed)
            history.append(VisualIteration(idx, current, observed, diffs))
            if not diffs:
                return VisualLoopResult(target, current, frame, observed, True, tuple(history))
            if idx >= max_repairs:
                break
            current = self.repairer.apply(current, target, diffs)
        return VisualLoopResult(target, current, frame, observed, False, tuple(history))
