from __future__ import annotations

from collections import deque
from typing import Any

from fap_visual.render import RasterFrame


class BoundedRasterVision:
    """Deterministic production-grade bounded raster observer.

    This backend observes rendered pixels only. It does not inspect the source
    VisualIR and does not reuse PrimitiveVision. The output is an object-list
    contract consumed by ObjectListVisionMapper through CallableVisionAdapter.

    Scope is intentionally bounded to solid RGB rectangles/circles rendered on
    a uniform background.
    """

    def __init__(self):
        self.observation_count = 0

    def observe(self, frame: RasterFrame) -> dict[str, Any]:
        self.observation_count += 1
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

        objects: list[dict[str, Any]] = []
        for index, (color, pixels) in enumerate(components):
            xs = [x for x, _ in pixels]
            ys = [y for _, y in pixels]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            fill = len(pixels) / max(1, width * height)

            if width == height and width >= 3 and width % 2 == 1 and fill < 0.90:
                radius = (width - 1) // 2
                objects.append(
                    {
                        "id": f"raster:{index}",
                        "kind": "circle",
                        "x": min_x + radius,
                        "y": min_y + radius,
                        "r": radius,
                        "rgb": list(color),
                    }
                )
            else:
                objects.append(
                    {
                        "id": f"raster:{index}",
                        "kind": "rect",
                        "x": min_x,
                        "y": min_y,
                        "w": width,
                        "h": height,
                        "rgb": list(color),
                    }
                )

        return {
            "objects": objects,
            "background": list(frame.background),
            "frame": {
                "width": frame.width,
                "height": frame.height,
            },
        }

    @staticmethod
    def _component(
        frame: RasterFrame,
        sx: int,
        sy: int,
        color: tuple[int, int, int],
        seen: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        queue = deque([(sx, sy)])
        seen.add((sx, sy))
        out: list[tuple[int, int]] = []
        while queue:
            x, y = queue.popleft()
            out.append((x, y))
            for nx, ny in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                if not (0 <= nx < frame.width and 0 <= ny < frame.height):
                    continue
                if (nx, ny) in seen:
                    continue
                if frame.pixel(nx, ny) != color:
                    continue
                seen.add((nx, ny))
                queue.append((nx, ny))
        return out
