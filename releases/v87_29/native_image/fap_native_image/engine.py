from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path
import random
import struct
import zlib

from fap_media_generation import GenerationRequest, MediaArtifact


class NativeImageError(RuntimeError):
    pass


_COLORS = {
    "red": (214, 62, 62), "赤": (214, 62, 62),
    "orange": (235, 132, 62), "オレンジ": (235, 132, 62),
    "yellow": (238, 205, 72), "黄": (238, 205, 72),
    "green": (72, 151, 91), "緑": (72, 151, 91),
    "blue": (66, 119, 190), "青": (66, 119, 190),
    "purple": (130, 91, 170), "紫": (130, 91, 170),
    "pink": (224, 133, 166), "ピンク": (224, 133, 166),
    "black": (24, 26, 30), "黒": (24, 26, 30),
    "white": (238, 240, 244), "白": (238, 240, 244),
    "gray": (132, 138, 145), "grey": (132, 138, 145), "灰": (132, 138, 145),
    "brown": (126, 88, 59), "茶": (126, 88, 59),
}


@dataclass(frozen=True)
class PromptPlan:
    prompt: str
    seed: int
    primary: tuple[int, int, int]
    secondary: tuple[int, int, int]
    night: bool
    sunset: bool
    water: bool
    mountains: bool
    trees: bool
    sun: bool
    moon: bool
    house: bool
    abstract: bool


class Raster:
    def __init__(self, width: int, height: int, bg=(255, 255, 255)):
        self.width = width
        self.height = height
        self.data = bytearray(bytes(bg) * (width * height))

    def set(self, x: int, y: int, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            i = (y * self.width + x) * 3
            self.data[i:i + 3] = bytes(color)

    def rect(self, x0, y0, x1, y1, color):
        x0, x1 = max(0, int(x0)), min(self.width, int(x1))
        y0, y1 = max(0, int(y0)), min(self.height, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for y in range(y0, y1):
            i = (y * self.width + x0) * 3
            self.data[i:i + len(row)] = row

    def gradient(self, top, bottom, y0=0, y1=None):
        if y1 is None:
            y1 = self.height
        y0, y1 = max(0, int(y0)), min(self.height, int(y1))
        span = max(1, y1 - y0 - 1)
        for y in range(y0, y1):
            t = (y - y0) / span
            c = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
            self.rect(0, y, self.width, y + 1, c)

    def circle(self, cx, cy, radius, color):
        cx, cy, radius = int(cx), int(cy), max(1, int(radius))
        r2 = radius * radius
        for y in range(max(0, cy - radius), min(self.height, cy + radius + 1)):
            dy = y - cy
            dx = int(math.sqrt(max(0, r2 - dy * dy)))
            self.rect(cx - dx, y, cx + dx + 1, y + 1, color)

    def triangle(self, p0, p1, p2, color):
        pts = sorted((p0, p1, p2), key=lambda p: p[1])
        (x0, y0), (x1, y1), (x2, y2) = pts
        def edge(xa, ya, xb, yb, y):
            if yb == ya:
                return xa
            return xa + (xb - xa) * ((y - ya) / (yb - ya))
        y_start = max(0, int(math.floor(y0)))
        y_end = min(self.height - 1, int(math.ceil(y2)))
        for y in range(y_start, y_end + 1):
            if y < y1:
                xa = edge(x0, y0, x1, y1, y)
                xb = edge(x0, y0, x2, y2, y)
            else:
                xa = edge(x1, y1, x2, y2, y)
                xb = edge(x0, y0, x2, y2, y)
            if xa > xb:
                xa, xb = xb, xa
            self.rect(int(xa), y, int(xb) + 1, y + 1, color)

    def line(self, x0, y0, x1, y1, color, width=1):
        x0, y0, x1, y1 = map(int, (x0, y0, x1, y1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.rect(x0 - width // 2, y0 - width // 2, x0 + width // 2 + 1, y0 + width // 2 + 1, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def png_bytes(self) -> bytes:
        def chunk(tag: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        stride = self.width * 3
        raw = bytearray()
        for y in range(self.height):
            raw.append(0)
            start = y * stride
            raw.extend(self.data[start:start + stride])
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b"")
        )


def _contains(text: str, *words: str) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


def _mix(a, b, t):
    return tuple(max(0, min(255, int(x + (y - x) * t))) for x, y in zip(a, b))


def _plan(prompt: str, constraints: tuple[str, ...]) -> PromptPlan:
    text = prompt + "\n" + "\n".join(constraints)
    digest = sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    found = [rgb for name, rgb in _COLORS.items() if name.lower() in text.lower()]
    primary = found[0] if found else (63 + digest[8] % 128, 63 + digest[9] % 128, 63 + digest[10] % 128)
    secondary = found[1] if len(found) > 1 else (63 + digest[11] % 128, 63 + digest[12] % 128, 63 + digest[13] % 128)
    night = _contains(text, "night", "夜", "星空", "midnight")
    sunset = _contains(text, "sunset", "夕焼", "夕日", "dusk")
    water = _contains(text, "water", "sea", "ocean", "lake", "river", "水", "海", "湖", "川")
    mountains = _contains(text, "mountain", "山", "峰")
    trees = _contains(text, "tree", "forest", "wood", "木", "森", "林")
    sun = _contains(text, "sun", "太陽", "日差し") or sunset
    moon = _contains(text, "moon", "月") or night
    house = _contains(text, "house", "home", "cabin", "家", "小屋")
    abstract = _contains(text, "abstract", "geometric", "pattern", "抽象", "幾何", "模様")
    if not any((water, mountains, trees, sun, moon, house, abstract)):
        abstract = True
    return PromptPlan(text, seed, primary, secondary, night, sunset, water, mountains, trees, sun, moon, house, abstract)


def _draw_scene(plan: PromptPlan, width: int, height: int, variant: int) -> Raster:
    rng = random.Random(plan.seed ^ (variant * 0x9E3779B97F4A7C15))
    img = Raster(width, height)

    if plan.night:
        top, bottom = (10, 18, 43), (42, 55, 88)
    elif plan.sunset:
        top, bottom = (93, 72, 142), (244, 145, 83)
    else:
        top, bottom = _mix(plan.primary, (190, 220, 245), 0.62), _mix(plan.secondary, (235, 243, 248), 0.72)
    img.gradient(top, bottom, 0, int(height * 0.72))

    horizon = int(height * (0.62 + rng.uniform(-0.04, 0.05)))
    ground = _mix(plan.secondary, (70, 102, 66), 0.56)
    img.rect(0, horizon, width, height, ground)

    if plan.night:
        for _ in range(max(24, (width * height) // 22000)):
            x, y = rng.randrange(width), rng.randrange(max(1, horizon))
            r = 1 if rng.random() < 0.85 else 2
            img.circle(x, y, r, (225, 230, 236))

    if plan.sun:
        sx = int(width * (0.72 if not plan.sunset else 0.78))
        sy = int(height * (0.20 if not plan.sunset else 0.42))
        img.circle(sx, sy, max(5, min(width, height) // 18), (246, 206, 88))

    if plan.moon:
        mx, my = int(width * 0.23), int(height * 0.20)
        mr = max(5, min(width, height) // 20)
        img.circle(mx, my, mr, (229, 231, 214))
        img.circle(mx + mr // 3, my - mr // 5, int(mr * 0.82), top)

    if plan.mountains:
        base = horizon + int(height * 0.04)
        count = 3 + rng.randrange(4)
        for i in range(count):
            cx = int((i + 0.5) * width / count + rng.uniform(-0.12, 0.12) * width / count)
            peak = int(height * rng.uniform(0.24, 0.45))
            half = int(width / count * rng.uniform(0.7, 1.25))
            c = _mix((70, 75, 88), plan.primary, 0.32 + 0.08 * (i % 3))
            img.triangle((cx - half, base), (cx, peak), (cx + half, base), c)
            if peak < height * 0.36:
                snow = _mix(c, (244, 244, 238), 0.78)
                img.triangle((cx - half * 0.22, int(peak + (base - peak) * 0.24)), (cx, peak), (cx + half * 0.22, int(peak + (base - peak) * 0.24)), snow)

    if plan.water:
        water_y = max(horizon, int(height * 0.58))
        water_c = _mix(plan.primary, (47, 111, 164), 0.64)
        img.gradient(_mix(water_c, (240, 180, 130), 0.15 if plan.sunset else 0.0), _mix(water_c, (10, 50, 90), 0.35), water_y, height)
        for _ in range(max(8, height // 35)):
            y = rng.randrange(water_y, height)
            x = rng.randrange(width)
            length = rng.randrange(max(4, width // 40), max(5, width // 12))
            img.line(x, y, min(width - 1, x + length), y, _mix(water_c, (235, 240, 245), 0.42), 1)

    if plan.trees:
        count = max(3, min(18, width // 90))
        for _ in range(count):
            x = rng.randrange(width)
            base = rng.randrange(int(height * 0.70), height)
            h = rng.randrange(max(18, height // 12), max(20, height // 4))
            trunk_w = max(2, width // 180)
            img.rect(x - trunk_w, base - h // 3, x + trunk_w + 1, base, (99, 69, 48))
            foliage = _mix((45, 112, 66), plan.primary, 0.18)
            img.triangle((x - h // 4, base - h // 5), (x, base - h), (x + h // 4, base - h // 5), foliage)
            img.triangle((x - h // 3, base), (x, base - int(h * 0.72)), (x + h // 3, base), _mix(foliage, (20, 70, 40), 0.20))

    if plan.house:
        hw, hh = max(30, width // 5), max(24, height // 6)
        x0, y0 = int(width * 0.56), int(height * 0.62)
        wall = _mix(plan.secondary, (210, 182, 143), 0.68)
        img.rect(x0, y0, min(width, x0 + hw), min(height, y0 + hh), wall)
        roof = _mix(plan.primary, (100, 55, 45), 0.55)
        img.triangle((x0 - hw * 0.08, y0), (x0 + hw * 0.5, y0 - hh * 0.48), (x0 + hw * 1.08, y0), roof)
        img.rect(x0 + int(hw * 0.42), y0 + int(hh * 0.48), x0 + int(hw * 0.60), y0 + hh, (80, 56, 43))

    if plan.abstract:
        for i in range(10 + min(20, (width + height) // 160)):
            c = _mix(plan.primary if i % 2 == 0 else plan.secondary, (245, 245, 245), rng.uniform(0.0, 0.38))
            if i % 3 == 0:
                img.circle(rng.randrange(width), rng.randrange(height), rng.randrange(max(4, min(width, height) // 40), max(5, min(width, height) // 8)), c)
            else:
                x0, y0 = rng.randrange(width), rng.randrange(height)
                img.line(x0, y0, rng.randrange(width), rng.randrange(height), c, max(1, min(width, height) // 180))

    return img


class NativeImageEngine:
    """FAP-owned prompt-to-raster engine.

    No pretrained checkpoint, network service, Pillow, NumPy, Torch or Diffusers
    is required. It is intentionally a small procedural generator, not a claim of
    photorealistic text-to-image quality.
    """

    def __init__(self, *, artifact_dir: str | Path):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.engine_id = "fap-native-raster-v1"
        self._generation_index = 0

    def probe(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "model_id": "fap-native-raster-v1",
            "license_id": "project-native",
            "offline": True,
            "external_weights": False,
            "external_runtime": False,
            "stdlib_only": True,
            "generation_kind": "procedural-prompt-to-raster",
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        if request.media_type != "image":
            raise NativeImageError("native image engine supports images only")
        self._generation_index += 1
        plan = _plan(prompt, request.constraints)
        image = _draw_scene(plan, request.width, request.height, self._generation_index)
        data = image.png_bytes()
        digest = sha256(data).hexdigest()
        path = self.artifact_dir / f"{digest}.png"
        path.write_bytes(data)
        return MediaArtifact(
            media_type="image",
            digest=digest,
            mime_type="image/png",
            locator=str(path),
            metadata={
                "engine_id": self.engine_id,
                "adapter": "fap-native-raster",
                "model_id": "fap-native-raster-v1",
                "offline": True,
                "external_weights": False,
                "stdlib_only": True,
                "bytes": len(data),
                "prompt_seed": plan.seed,
            },
        )
