from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .visual_ir import RGB, VisualIR


@dataclass(frozen=True)
class RasterFrame:
    width: int
    height: int
    pixels: tuple[tuple[RGB, ...], ...]
    background: RGB

    def pixel(self, x: int, y: int) -> RGB:
        return self.pixels[y][x]


class RendererPort(Protocol):
    def render(self, ir: VisualIR) -> RasterFrame: ...


class SmallRasterRenderer:
    """Dependency-free renderer for Visual Primitives. It never plans content itself."""

    def render(self, ir: VisualIR) -> RasterFrame:
        ir.validate()
        rows = [[ir.background for _ in range(ir.width)] for _ in range(ir.height)]
        for p in ir.primitives:
            if p.kind == "rect":
                for yy in range(p.y, p.y + p.height):
                    for xx in range(p.x, p.x + p.width):
                        self._put(rows, xx, yy, p.color)
            elif p.kind == "circle":
                rr = p.radius * p.radius
                for yy in range(p.y - p.radius, p.y + p.radius + 1):
                    for xx in range(p.x - p.radius, p.x + p.radius + 1):
                        if (xx - p.x) ** 2 + (yy - p.y) ** 2 <= rr:
                            self._put(rows, xx, yy, p.color)
        return RasterFrame(ir.width, ir.height, tuple(tuple(row) for row in rows), ir.background)

    @staticmethod
    def _put(rows: list[list[RGB]], x: int, y: int, color: RGB) -> None:
        if 0 <= y < len(rows) and 0 <= x < len(rows[0]):
            rows[y][x] = color


class CallableRendererAdapter:
    """Swap point for an external renderer/diffusion backend without making it mandatory."""

    def __init__(self, fn):
        if not callable(fn):
            raise TypeError("renderer callback must be callable")
        self.fn = fn

    def render(self, ir: VisualIR) -> RasterFrame:
        frame = self.fn(ir)
        if not isinstance(frame, RasterFrame):
            raise TypeError("external renderer must return RasterFrame")
        return frame
