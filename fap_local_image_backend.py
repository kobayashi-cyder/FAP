from __future__ import annotations

import datetime as dt
import json
import math
import re
import struct
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def _compact(text: str) -> str:
    return re.sub(r"[\s\-‐‑–—_・･、。，．,:：;；!?！？'\"]+", "", _norm(text))


def _hex_color(value: str, default=(40, 40, 40)) -> tuple[int, int, int]:
    v = str(value or "").strip().lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    if len(v) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", v):
        return default
    return tuple(int(v[i:i+2], 16) for i in (0, 2, 4))


@dataclass(frozen=True)
class VisualConcept:
    concept_id: str
    label: str
    aliases: tuple[str, ...]
    primitives: tuple[dict[str, Any], ...]
    background: str
    caption: str


class VisualKnowledge:
    """Declarative visual concepts loaded from knowledge/*.jsonl.

    Subject knowledge is data. Renderer code knows only generic primitives.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.concepts: tuple[VisualConcept, ...] = ()
        self._load()

    def _load(self) -> None:
        rows: list[VisualConcept] = []
        folder = self.root / "knowledge"
        if not folder.exists():
            self.concepts = ()
            return
        for path in sorted(folder.rglob("*.jsonl")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in lines:
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if not isinstance(item, dict) or item.get("kind") != "visual_concept":
                    continue
                cid = str(item.get("id") or "").strip()
                aliases = tuple(str(x) for x in (item.get("aliases") or []) if str(x).strip())
                primitives = tuple(x for x in (item.get("primitives") or []) if isinstance(x, dict))
                if cid and aliases and primitives:
                    rows.append(VisualConcept(
                        concept_id=cid,
                        label=str(item.get("label") or cid),
                        aliases=aliases,
                        primitives=primitives,
                        background=str(item.get("background") or "#eef2e8"),
                        caption=str(item.get("caption") or item.get("label") or cid),
                    ))
        self.concepts = tuple(rows)

    def resolve(self, text: str) -> tuple[VisualConcept | None, float]:
        value = _compact(text)
        ranked: list[tuple[float, VisualConcept]] = []
        for concept in self.concepts:
            best = 0.0
            for alias in concept.aliases:
                token = _compact(alias)
                if token and token in value:
                    best = max(best, 4.0 + min(3.0, len(token) / 3.0))
            if best:
                ranked.append((best, concept))
        ranked.sort(key=lambda x: (-x[0], x[1].concept_id))
        return (ranked[0][1], ranked[0][0]) if ranked else (None, 0.0)


class Canvas:
    def __init__(self, width: int, height: int, background: str):
        self.width = int(width)
        self.height = int(height)
        bg = _hex_color(background, (240, 244, 236))
        self.pixels = bytearray(bg * (self.width * self.height))

    def _blend(self, x: int, y: int, rgb: tuple[int, int, int], alpha: float = 1.0) -> None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        a = max(0.0, min(1.0, float(alpha)))
        i = (y * self.width + x) * 3
        if a >= 0.999:
            self.pixels[i:i+3] = bytes(rgb)
            return
        for j, v in enumerate(rgb):
            self.pixels[i+j] = int(round(self.pixels[i+j] * (1.0 - a) + v * a))

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, fill: str, alpha: float = 1.0) -> None:
        rgb = _hex_color(fill)
        x0 = max(0, int(math.floor(cx - rx)))
        x1 = min(self.width - 1, int(math.ceil(cx + rx)))
        y0 = max(0, int(math.floor(cy - ry)))
        y1 = min(self.height - 1, int(math.ceil(cy + ry)))
        if rx <= 0 or ry <= 0:
            return
        invx = 1.0 / (rx * rx)
        invy = 1.0 / (ry * ry)
        for y in range(y0, y1 + 1):
            dy = y + 0.5 - cy
            dy2 = dy * dy * invy
            if dy2 > 1.0:
                continue
            span = rx * math.sqrt(max(0.0, 1.0 - dy2))
            xa = max(x0, int(math.floor(cx - span)))
            xb = min(x1, int(math.ceil(cx + span)))
            for x in range(xa, xb + 1):
                dx = x + 0.5 - cx
                if dx * dx * invx + dy2 <= 1.0:
                    self._blend(x, y, rgb, alpha)

    def rect(self, x: float, y: float, w: float, h: float, fill: str, alpha: float = 1.0) -> None:
        rgb = _hex_color(fill)
        x0 = max(0, int(round(x)))
        y0 = max(0, int(round(y)))
        x1 = min(self.width, int(round(x + w)))
        y1 = min(self.height, int(round(y + h)))
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                self._blend(xx, yy, rgb, alpha)

    def polygon(self, points: list[tuple[float, float]], fill: str, alpha: float = 1.0) -> None:
        if len(points) < 3:
            return
        rgb = _hex_color(fill)
        ys = [p[1] for p in points]
        y0 = max(0, int(math.floor(min(ys))))
        y1 = min(self.height - 1, int(math.ceil(max(ys))))
        n = len(points)
        for y in range(y0, y1 + 1):
            scan = y + 0.5
            xs: list[float] = []
            for i in range(n):
                x1, y1p = points[i]
                x2, y2p = points[(i + 1) % n]
                if (y1p <= scan < y2p) or (y2p <= scan < y1p):
                    if y2p != y1p:
                        xs.append(x1 + (scan - y1p) * (x2 - x1) / (y2p - y1p))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa = max(0, int(math.ceil(xs[i])))
                xb = min(self.width - 1, int(math.floor(xs[i + 1])))
                for x in range(xa, xb + 1):
                    self._blend(x, y, rgb, alpha)

    def line(self, x1: float, y1: float, x2: float, y2: float, width: float, fill: str, alpha: float = 1.0) -> None:
        rgb = _hex_color(fill)
        dx = x2 - x1
        dy = y2 - y1
        steps = max(1, int(max(abs(dx), abs(dy))))
        radius = max(1, int(round(width / 2)))
        for step in range(steps + 1):
            t = step / steps
            cx = x1 + dx * t
            cy = y1 + dy * t
            for yy in range(int(cy) - radius, int(cy) + radius + 1):
                for xx in range(int(cx) - radius, int(cx) + radius + 1):
                    if (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2:
                        self._blend(xx, yy, rgb, alpha)

    def png_bytes(self) -> bytes:
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            start = y * stride
            raw.extend(self.pixels[start:start + stride])

        def chunk(kind: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + kind
                + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
            )

        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b"")
        )


class LocalRasterGenerator:
    """Self-contained stdlib image generator.

    It renders declarative scene graphs to PNG without a model server, Pillow,
    network access, or third-party image-generation API. Quality is deliberately
    described as schematic/illustrative rather than photorealistic.
    """

    def __init__(self, root: Path, artifact_dir: Path):
        self.root = Path(root)
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge = VisualKnowledge(self.root)

    def available(self) -> tuple[bool, str]:
        if not self.knowledge.concepts:
            return False, "内蔵画像知識が空です。"
        return True, f"FAP内蔵ラスタ生成器が利用可能です（concepts={len(self.knowledge.concepts)}）。"

    @staticmethod
    def _xy(v: Any, scale: float, offset: float = 0.0) -> float:
        return offset + float(v) * scale

    def _render_primitive(self, canvas: Canvas, primitive: dict[str, Any]) -> None:
        kind = str(primitive.get("type") or "")
        fill = str(primitive.get("fill") or "#333333")
        alpha = float(primitive.get("alpha", 1.0))
        w, h = canvas.width, canvas.height

        if kind == "ellipse":
            canvas.ellipse(
                self._xy(primitive.get("cx", 0.5), w),
                self._xy(primitive.get("cy", 0.5), h),
                self._xy(primitive.get("rx", 0.1), w),
                self._xy(primitive.get("ry", 0.1), h),
                fill,
                alpha,
            )
        elif kind == "rect":
            canvas.rect(
                self._xy(primitive.get("x", 0.0), w),
                self._xy(primitive.get("y", 0.0), h),
                self._xy(primitive.get("w", 0.1), w),
                self._xy(primitive.get("h", 0.1), h),
                fill,
                alpha,
            )
        elif kind == "polygon":
            pts = []
            for pair in primitive.get("points") or []:
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    pts.append((self._xy(pair[0], w), self._xy(pair[1], h)))
            canvas.polygon(pts, fill, alpha)
        elif kind == "line":
            canvas.line(
                self._xy(primitive.get("x1", 0.0), w),
                self._xy(primitive.get("y1", 0.0), h),
                self._xy(primitive.get("x2", 1.0), w),
                self._xy(primitive.get("y2", 1.0), h),
                max(1.0, self._xy(primitive.get("width", 0.01), min(w, h))),
                fill,
                alpha,
            )

    def generate(self, text: str, width: int = 512, height: int = 512) -> dict:
        concept, score = self.knowledge.resolve(text)
        if concept is None:
            return {
                "ok": False,
                "reply": "画像生成要求は認識しましたが、内蔵ラスタ生成器に対応する視覚概念がまだありません。",
                "confidence": 0.78,
                "local_raster": True,
                "structural_verified": False,
            }

        width = max(256, min(768, int(width)))
        height = max(256, min(768, int(height)))
        canvas = Canvas(width, height, concept.background)
        for primitive in concept.primitives:
            self._render_primitive(canvas, primitive)

        raw = canvas.png_bytes()
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return {
                "ok": False,
                "reply": "内蔵ラスタ生成器がPNG検証に失敗しました。",
                "confidence": 0.60,
                "local_raster": True,
                "structural_verified": False,
            }

        name = "img_local_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png"
        path = self.artifact_dir / name
        path.write_bytes(raw)
        size_ok = path.exists() and path.stat().st_size > 100
        if not size_ok:
            return {
                "ok": False,
                "reply": "内蔵ラスタ生成器は描画しましたが、成果物検証に失敗しました。",
                "confidence": 0.60,
                "local_raster": True,
                "structural_verified": False,
            }

        return {
            "ok": True,
            "reply": (
                f"FAP内蔵ラスタ生成器で「{concept.label}」の画像を生成しました。\n"
                "外部画像APIは使用していません。現在は軽量な図解・イラスト生成で、写真品質の生成モデルではありません。"
            ),
            "confidence": 0.94,
            "local_raster": True,
            "image_orchestrated": True,
            "structural_verified": True,
            "visual_verified": False,
            "image_score": min(0.95, 0.82 + score / 100.0),
            "visual_caption": concept.caption,
            "concept_id": concept.concept_id,
            "candidate_count": 1,
            "generation_rounds": 1,
            "artifacts": [{"type": "image", "src": "/artifacts/" + name, "name": name}],
        }
