from __future__ import annotations

import re
from dataclasses import dataclass

from .visual_ir import RGB, VisualIR, VisualPrimitive


COLORS: dict[str, RGB] = {
    "red": (255, 0, 0), "赤": (255, 0, 0), "赤い": (255, 0, 0),
    "blue": (0, 0, 255), "青": (0, 0, 255), "青い": (0, 0, 255),
    "green": (0, 180, 0), "緑": (0, 180, 0), "緑の": (0, 180, 0),
    "yellow": (255, 220, 0), "黄": (255, 220, 0), "黄色": (255, 220, 0),
    "black": (0, 0, 0), "黒": (0, 0, 0), "黒い": (0, 0, 0),
    "white": (255, 255, 255), "白": (255, 255, 255), "白い": (255, 255, 255),
}


@dataclass(frozen=True)
class NaturalLanguageVisualPlanner:
    default_width: int = 64
    default_height: int = 64

    def plan(self, text: str) -> VisualIR:
        text = str(text or "").strip()
        if not text:
            raise ValueError("visual instruction is empty")
        canvas = self._canvas(text)
        chunks = [x.strip() for x in re.split(r"[;；\n]+", text) if x.strip()]
        primitives: list[VisualPrimitive] = []
        for chunk in chunks:
            kind = self._kind(chunk)
            if not kind:
                continue
            color = self._color(chunk)
            x = self._number(chunk, "x", 0)
            y = self._number(chunk, "y", 0)
            if kind == "circle":
                radius = self._number(chunk, "r", self._number(chunk, "radius", 3))
                primitives.append(VisualPrimitive(f"p{len(primitives)}", "circle", x, y, radius * 2 + 1, radius * 2 + 1, radius, color))
            else:
                width = self._number(chunk, "w", self._number(chunk, "width", 5))
                height = self._number(chunk, "h", self._number(chunk, "height", 5))
                primitives.append(VisualPrimitive(f"p{len(primitives)}", "rect", x, y, width, height, 0, color))
        if not primitives:
            raise ValueError("no supported shape found in visual instruction")
        ir = VisualIR(canvas[0], canvas[1], tuple(primitives))
        ir.validate()
        return ir

    def _canvas(self, text: str) -> tuple[int, int]:
        m = re.search(r"canvas\s*=\s*(\d+)\s*[x×]\s*(\d+)", text, re.I)
        if not m:
            m = re.search(r"キャンバス\s*=\s*(\d+)\s*[x×]\s*(\d+)", text)
        if not m:
            return self.default_width, self.default_height
        return int(m.group(1)), int(m.group(2))

    @staticmethod
    def _number(text: str, key: str, default: int) -> int:
        m = re.search(rf"(?:^|[\s,(]){re.escape(key)}\s*=\s*(-?\d+)", text, re.I)
        return int(m.group(1)) if m else int(default)

    @staticmethod
    def _kind(text: str) -> str | None:
        low = text.lower()
        if any(token in low for token in ("circle", "円", "丸")):
            return "circle"
        if any(token in low for token in ("rectangle", "rect", "長方形", "四角", "矩形")):
            return "rect"
        return None

    @staticmethod
    def _color(text: str) -> RGB:
        low = text.lower()
        for name, value in COLORS.items():
            if name.lower() in low:
                return value
        m = re.search(r"#([0-9a-fA-F]{6})", text)
        if m:
            raw = m.group(1)
            return int(raw[:2], 16), int(raw[2:4], 16), int(raw[4:], 16)
        return (0, 0, 0)
