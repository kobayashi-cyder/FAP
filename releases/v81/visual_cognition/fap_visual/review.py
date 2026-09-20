from __future__ import annotations

from dataclasses import dataclass, replace
import math

from .visual_ir import VisualIR, VisualPrimitive


@dataclass(frozen=True)
class VisualDifference:
    primitive_id: str
    field: str
    expected: object
    actual: object
    magnitude: float


class VisualDiffer:
    """Structured target-vs-Vision comparison. It matches locally, then emits field-level diffs."""

    def compare(self, target: VisualIR, observed: VisualIR) -> tuple[VisualDifference, ...]:
        target.validate()
        observed.validate()
        diffs: list[VisualDifference] = []
        unmatched = list(observed.primitives)
        for expected in target.primitives:
            actual = self._nearest(expected, unmatched)
            if actual is None:
                diffs.append(VisualDifference(expected.primitive_id, "missing", expected, None, 1.0))
                continue
            unmatched.remove(actual)
            if expected.kind != actual.kind:
                diffs.append(VisualDifference(expected.primitive_id, "kind", expected.kind, actual.kind, 1.0))
            if expected.color != actual.color:
                d = math.sqrt(sum((a - b) ** 2 for a, b in zip(expected.color, actual.color))) / 441.673
                diffs.append(VisualDifference(expected.primitive_id, "color", expected.color, actual.color, round(d, 4)))
            if (expected.x, expected.y) != (actual.x, actual.y):
                d = math.hypot(expected.x - actual.x, expected.y - actual.y) / max(1.0, math.hypot(target.width, target.height))
                diffs.append(VisualDifference(expected.primitive_id, "position", (expected.x, expected.y), (actual.x, actual.y), round(d, 4)))
            if expected.kind == actual.kind == "circle" and expected.radius != actual.radius:
                diffs.append(VisualDifference(expected.primitive_id, "radius", expected.radius, actual.radius, abs(expected.radius - actual.radius)))
            if expected.kind == actual.kind == "rect" and (expected.width, expected.height) != (actual.width, actual.height):
                diffs.append(VisualDifference(expected.primitive_id, "size", (expected.width, expected.height), (actual.width, actual.height), float(abs(expected.width-actual.width)+abs(expected.height-actual.height))))
        for extra in unmatched:
            diffs.append(VisualDifference("", "extra", None, extra, 1.0))
        return tuple(diffs)

    @staticmethod
    def _nearest(expected: VisualPrimitive, candidates: list[VisualPrimitive]) -> VisualPrimitive | None:
        if not candidates:
            return None
        same_kind = [p for p in candidates if p.kind == expected.kind]
        pool = same_kind or candidates
        ex, ey = expected.center
        return min(pool, key=lambda p: (p.center[0] - ex) ** 2 + (p.center[1] - ey) ** 2)


class LocalVisualRepairer:
    """Repairs only primitives/fields identified by VisualDiffer."""

    def apply(self, draft: VisualIR, target: VisualIR, diffs: tuple[VisualDifference, ...]) -> VisualIR:
        out = draft
        by_id: dict[str, set[str]] = {}
        for diff in diffs:
            if diff.primitive_id:
                by_id.setdefault(diff.primitive_id, set()).add(diff.field)
        for primitive_id, fields in by_id.items():
            expected = target.get(primitive_id)
            try:
                current = out.get(primitive_id)
            except KeyError:
                out = replace(out, primitives=out.primitives + (expected,))
                continue
            if "kind" in fields:
                current = expected
            else:
                if "color" in fields:
                    current = replace(current, color=expected.color)
                if "position" in fields:
                    current = replace(current, x=expected.x, y=expected.y)
                if "radius" in fields:
                    current = replace(current, radius=expected.radius, width=expected.width, height=expected.height)
                if "size" in fields:
                    current = replace(current, width=expected.width, height=expected.height)
            out = out.replace_primitive(primitive_id, current)
        out.validate()
        return out
