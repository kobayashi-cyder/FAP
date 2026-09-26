from __future__ import annotations

from collections import deque
from typing import Any, Callable, Optional, Protocol

from .render import RasterFrame
from .visual_ir import VisualIR, VisualPrimitive


class VisionPort(Protocol):
    def observe(self, frame: RasterFrame) -> VisualIR: ...


class CallableVisionAdapter:
    """Bridge an existing Vision implementation into the shared VisualIR state space.

    If the existing Vision already returns VisualIR, no mapper is needed.
    Otherwise mapper(raw_vision_output, frame) must normalize it to VisualIR.
    """

    def __init__(
        self,
        fn: Callable[[RasterFrame], Any],
        *,
        mapper: Optional[Callable[[Any, RasterFrame], VisualIR]] = None,
    ):
        if not callable(fn):
            raise TypeError("vision callback must be callable")
        if mapper is not None and not callable(mapper):
            raise TypeError("vision mapper must be callable")
        self.fn = fn
        self.mapper = mapper

    def observe(self, frame: RasterFrame) -> VisualIR:
        raw = self.fn(frame)
        if isinstance(raw, VisualIR):
            observed = raw
        elif self.mapper is not None:
            observed = self.mapper(raw, frame)
        else:
            raise TypeError("existing Vision output requires a mapper to VisualIR")
        if not isinstance(observed, VisualIR):
            raise TypeError("Vision mapper must return VisualIR")
        observed.validate()
        return observed


class PrimitiveVision:
    """Deterministic bootstrap Vision used only for dependency-free verification."""

    def observe(self, frame: RasterFrame) -> VisualIR:
        seen: set[tuple[int, int]] = set()
        components: list[tuple[tuple[int, int, int], list[tuple[int, int]]]] = []
        for y in range(frame.height):
            for x in range(frame.width):
                color = frame.pixel(x, y)
                if color == frame.background or (x, y) in seen:
                    continue
                pixels = self._component(frame, x, y, color, seen)
                components.append((color, pixels))
        components.sort(
            key=lambda item: (
                min(y for _, y in item[1]),
                min(x for x, _ in item[1]),
                item[0],
            )
        )
        primitives: list[VisualPrimitive] = []
        for idx, (color, pixels) in enumerate(components):
            xs = [p[0] for p in pixels]
            ys = [p[1] for p in pixels]
            min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
            width, height = max_x - min_x + 1, max_y - min_y + 1
            fill = len(pixels) / max(1, width * height)
            if width == height and width >= 3 and fill < 0.90:
                radius = (width - 1) // 2
                primitives.append(
                    VisualPrimitive(
                        f"v{idx}", "circle",
                        min_x + radius, min_y + radius,
                        width, height, radius, color,
                    )
                )
            else:
                primitives.append(
                    VisualPrimitive(
                        f"v{idx}", "rect",
                        min_x, min_y, width, height, 0, color,
                    )
                )
        observed = VisualIR(frame.width, frame.height, tuple(primitives), frame.background)
        observed.validate()
        return observed

    @staticmethod
    def _component(
        frame: RasterFrame,
        sx: int,
        sy: int,
        color,
        seen: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        q = deque([(sx, sy)])
        seen.add((sx, sy))
        out: list[tuple[int, int]] = []
        while q:
            x, y = q.popleft()
            out.append((x, y))
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if not (0 <= nx < frame.width and 0 <= ny < frame.height):
                    continue
                if (nx, ny) in seen or frame.pixel(nx, ny) != color:
                    continue
                seen.add((nx, ny))
                q.append((nx, ny))
        return out
