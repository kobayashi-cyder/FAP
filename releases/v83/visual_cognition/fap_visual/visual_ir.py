from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

RGB = tuple[int, int, int]


def rgb(r: int, g: int, b: int) -> RGB:
    return tuple(max(0, min(255, int(x))) for x in (r, g, b))  # type: ignore[return-value]


@dataclass(frozen=True)
class VisualPrimitive:
    primitive_id: str
    kind: str
    x: int
    y: int
    width: int = 1
    height: int = 1
    radius: int = 0
    color: RGB = (0, 0, 0)

    def validate(self) -> None:
        if not self.primitive_id:
            raise ValueError("primitive_id is required")
        if self.kind not in {"rect", "circle"}:
            raise ValueError(f"unsupported visual primitive: {self.kind}")
        if self.width < 1 or self.height < 1:
            raise ValueError("width/height must be positive")
        if self.kind == "circle" and self.radius < 1:
            raise ValueError("circle radius must be positive")
        if len(self.color) != 3 or any((not isinstance(c, int)) or c < 0 or c > 255 for c in self.color):
            raise ValueError("color must be RGB bytes")

    @property
    def center(self) -> tuple[float, float]:
        if self.kind == "circle":
            return float(self.x), float(self.y)
        return self.x + (self.width - 1) / 2.0, self.y + (self.height - 1) / 2.0


@dataclass(frozen=True)
class MotionPrimitive:
    target_id: str
    kind: str
    start: float
    end: float
    dx: int = 0
    dy: int = 0

    def validate(self) -> None:
        if self.kind != "translate":
            raise ValueError(f"unsupported motion primitive: {self.kind}")
        if self.end <= self.start:
            raise ValueError("motion end must be after start")

    def progress(self, t: float) -> float:
        if t <= self.start:
            return 0.0
        if t >= self.end:
            return 1.0
        return (float(t) - self.start) / (self.end - self.start)


@dataclass(frozen=True)
class VisualIR:
    width: int
    height: int
    primitives: tuple[VisualPrimitive, ...]
    background: RGB = (255, 255, 255)
    motions: tuple[MotionPrimitive, ...] = ()
    duration: float = 0.0

    def validate(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError("canvas dimensions must be positive")
        ids: set[str] = set()
        for primitive in self.primitives:
            primitive.validate()
            if primitive.primitive_id in ids:
                raise ValueError("duplicate primitive_id")
            ids.add(primitive.primitive_id)
        for motion in self.motions:
            motion.validate()
            if motion.target_id not in ids:
                raise ValueError(f"motion target not found: {motion.target_id}")
        if self.duration < 0:
            raise ValueError("duration must be non-negative")

    def get(self, primitive_id: str) -> VisualPrimitive:
        for primitive in self.primitives:
            if primitive.primitive_id == primitive_id:
                return primitive
        raise KeyError(primitive_id)

    def replace_primitive(self, primitive_id: str, replacement: VisualPrimitive) -> "VisualIR":
        replacement.validate()
        found = False
        out: list[VisualPrimitive] = []
        for primitive in self.primitives:
            if primitive.primitive_id == primitive_id:
                out.append(replacement)
                found = True
            else:
                out.append(primitive)
        if not found:
            raise KeyError(primitive_id)
        result = replace(self, primitives=tuple(out))
        result.validate()
        return result

    def sample(self, t: float) -> "VisualIR":
        self.validate()
        state = {p.primitive_id: p for p in self.primitives}
        for motion in self.motions:
            p = state[motion.target_id]
            k = motion.progress(t)
            state[motion.target_id] = replace(
                p,
                x=p.x + round(motion.dx * k),
                y=p.y + round(motion.dy * k),
            )
        return replace(
            self,
            primitives=tuple(state[p.primitive_id] for p in self.primitives),
            motions=(),
        )


def with_primitives(
    width: int,
    height: int,
    primitives: Iterable[VisualPrimitive],
    *,
    background: RGB = (255, 255, 255),
) -> VisualIR:
    ir = VisualIR(width, height, tuple(primitives), background)
    ir.validate()
    return ir
