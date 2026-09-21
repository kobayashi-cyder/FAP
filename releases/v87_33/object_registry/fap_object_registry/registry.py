from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Callable, Iterable, Sequence

from fap_human_lbs.core import (
    Face,
    Mesh,
    Pose,
    Vertex,
    build_human_mesh,
    default_human_skeleton,
    pose_from_prompt,
    skinned_positions,
    v_add,
)
from fap_scene_image.scene import (
    add_static_ellipsoid,
    add_static_quad,
    add_static_tube,
)


Vec3 = tuple[float, float, float]
Color = tuple[int, int, int]


@dataclass(frozen=True)
class ScenePlan:
    required_objects: tuple[str, ...]
    supported_objects: tuple[str, ...]
    unsupported_objects: tuple[str, ...]
    requested_styles: tuple[str, ...]
    centered_subjects: bool
    source_text: str


_OBJECT_PATTERNS = (
    ("human", re.compile(r"(?:^|[^A-Za-z])(?:人|人物|人間|男性|女性|男の人|女の人)(?:$|[^A-Za-z])|\b(?:person|people|human|man|woman)\b", re.I)),
    ("dog", re.compile(r"犬|わんこ|ワンコ|ビーグル|\b(?:dog|beagle|puppy)\b", re.I)),
    ("bird", re.compile(r"鳥|小鳥|野鳥|\b(?:bird|sparrow|pigeon|eagle)\b", re.I)),
    ("cat", re.compile(r"猫|ネコ|ねこ|\b(?:cat|kitten)\b", re.I)),
    ("horse", re.compile(r"馬|ウマ|\bhorse\b", re.I)),
    ("car", re.compile(r"車|自動車|乗用車|\b(?:car|automobile|vehicle)\b", re.I)),
)


def parse_scene_plan(prompt: str, constraints: Sequence[str] = ()) -> ScenePlan:
    text = "\n".join([str(prompt or ""), *(str(x or "") for x in constraints)])
    required = [kind for kind, pattern in _OBJECT_PATTERNS if pattern.search(text)]

    styles: list[str] = []
    if re.search(
        r"写真風|写真のよう|フォトリアル|写実|実写|\b(?:photo|photoreal|photorealistic|realistic photo)\b",
        text,
        re.I,
    ):
        styles.append("photorealistic")
    if re.search(r"イラスト|漫画|アニメ|\b(?:illustration|anime|cartoon)\b", text, re.I):
        styles.append("illustration")
    if not styles:
        styles.append("geometric-3d")

    centered = bool(re.search(r"中央|中心|センター|\bcenter(?:ed)?\b", text, re.I))
    supported = [x for x in required if x in OBJECT_BUILDERS or x == "human"]
    unsupported = [x for x in required if x not in supported]
    return ScenePlan(
        required_objects=tuple(required),
        supported_objects=tuple(supported),
        unsupported_objects=tuple(unsupported),
        requested_styles=tuple(styles),
        centered_subjects=centered,
        source_text=text,
    )


def _triangle(mesh: Mesh, a: Vec3, b: Vec3, c: Vec3, color: Color) -> None:
    start = len(mesh.vertices)
    mesh.vertices.extend((Vertex(a, ()), Vertex(b, ()), Vertex(c, ())))
    mesh.faces.append(Face(start, start + 1, start + 2, color))


def _box(mesh: Mesh, center: Vec3, half: Vec3, color: Color) -> None:
    cx, cy, cz = center
    hx, hy, hz = half
    points = (
        (cx-hx, cy-hy, cz-hz), (cx+hx, cy-hy, cz-hz),
        (cx+hx, cy+hy, cz-hz), (cx-hx, cy+hy, cz-hz),
        (cx-hx, cy-hy, cz+hz), (cx+hx, cy-hy, cz+hz),
        (cx+hx, cy+hy, cz+hz), (cx-hx, cy+hy, cz+hz),
    )
    start = len(mesh.vertices)
    mesh.vertices.extend(Vertex(p, ()) for p in points)
    quads = (
        (0,1,2,3), (4,7,6,5), (0,4,5,1),
        (3,2,6,7), (1,5,6,2), (0,3,7,4),
    )
    for a,b,c,d in quads:
        mesh.faces.append(Face(start+a, start+b, start+c, color))
        mesh.faces.append(Face(start+a, start+c, start+d, color))


def build_dog_mesh(*, x: float = 0.0, y: float = -1.05) -> Mesh:
    mesh = Mesh()
    brown = (145, 101, 70)
    dark = (76, 57, 48)
    tan = (190, 142, 98)
    cream = (226, 218, 198)
    black = (35, 32, 30)

    add_static_ellipsoid(mesh, (x, y, 0.0), (0.58, 0.29, 0.27), brown, rings=8, sides=14)
    add_static_ellipsoid(mesh, (x - 0.08, y + 0.08, -0.02), (0.42, 0.18, 0.28), dark, rings=7, sides=13)
    add_static_tube(mesh, (x + 0.40, y + 0.06, 0.0), (x + 0.60, y + 0.28, 0.0), 0.18, 0.16, tan)
    add_static_ellipsoid(mesh, (x + 0.70, y + 0.32, 0.0), (0.27, 0.24, 0.23), tan, rings=7, sides=12)
    add_static_ellipsoid(mesh, (x + 0.94, y + 0.24, -0.01), (0.24, 0.14, 0.16), cream, rings=6, sides=10)
    add_static_ellipsoid(mesh, (x + 1.12, y + 0.25, -0.02), (0.06, 0.05, 0.055), black, rings=4, sides=8)
    add_static_ellipsoid(mesh, (x + 0.69, y + 0.38, -0.205), (0.03, 0.03, 0.02), black, rings=4, sides=7)
    add_static_ellipsoid(mesh, (x + 0.58, y + 0.20, -0.23), (0.11, 0.24, 0.05), dark, rings=5, sides=8)
    add_static_ellipsoid(mesh, (x + 0.58, y + 0.20, 0.23), (0.11, 0.24, 0.05), dark, rings=5, sides=8)

    for lx, lz in ((x+0.33,-0.16),(x+0.48,0.16),(x-0.36,-0.16),(x-0.20,0.16)):
        hip = (lx, y - 0.18, lz)
        ankle = (lx + (0.03 if lx > x else -0.03), -1.66, lz)
        add_static_tube(mesh, hip, ankle, 0.09, 0.06, cream, sides=8)
        add_static_ellipsoid(mesh, (ankle[0]+0.07, -1.75, lz), (0.12,0.065,0.095), cream, rings=4, sides=8)

    add_static_tube(mesh, (x-0.52,y+0.08,0.02), (x-0.92,y+0.38,0.02), 0.07,0.035,brown,sides=8)
    add_static_tube(mesh, (x-0.92,y+0.38,0.02), (x-1.08,y+0.49,0.02), 0.035,0.017,cream,sides=8)
    mesh.validate()
    return mesh


def build_bird_mesh(*, x: float = 0.0, y: float = -1.16) -> Mesh:
    """Native side-profile bird with body, wing, head, beak, tail and legs."""
    mesh = Mesh()
    body = (118, 144, 165)
    wing = (72, 94, 116)
    head = (137, 157, 174)
    beak = (221, 166, 64)
    leg = (171, 112, 67)
    black = (28, 28, 26)

    add_static_ellipsoid(mesh, (x, y, 0.0), (0.45, 0.27, 0.23), body, rings=8, sides=14)
    add_static_ellipsoid(mesh, (x+0.33, y+0.20, -0.01), (0.21,0.20,0.19), head, rings=7, sides=12)
    add_static_tube(mesh, (x+0.47,y+0.18,-0.01), (x+0.70,y+0.16,-0.01), 0.075,0.012,beak,sides=8)
    add_static_ellipsoid(mesh, (x+0.38,y+0.26,-0.175), (0.028,0.028,0.018), black, rings=4, sides=7)

    # Visible front-side wing and layered tail.
    add_static_ellipsoid(mesh, (x-0.07,y+0.01,-0.205), (0.31,0.18,0.055), wing, rings=6, sides=11)
    _triangle(mesh, (x-0.34,y-0.02,-0.02), (x-0.78,y+0.08,-0.02), (x-0.50,y-0.18,-0.02), wing)
    _triangle(mesh, (x-0.34,y+0.02,0.04), (x-0.73,y+0.18,0.04), (x-0.48,y-0.10,0.04), body)

    # Legs and small feet.
    for lx in (x-0.10, x+0.10):
        add_static_tube(mesh, (lx,y-0.21,-0.03), (lx,-1.63,-0.03), 0.025,0.018,leg,sides=6)
        add_static_tube(mesh, (lx,-1.63,-0.03), (lx+0.11,-1.68,-0.05), 0.018,0.008,leg,sides=6)
        add_static_tube(mesh, (lx,-1.63,-0.03), (lx-0.08,-1.68,-0.05), 0.018,0.008,leg,sides=6)
    mesh.validate()
    return mesh


def build_cat_mesh(*, x: float = 0.0, y: float = -1.08) -> Mesh:
    mesh = Mesh()
    fur = (153, 141, 128)
    dark = (75, 69, 64)
    cream = (219, 208, 192)
    black = (28, 28, 26)

    add_static_ellipsoid(mesh, (x,y,0.0), (0.52,0.27,0.25), fur, rings=8, sides=14)
    add_static_ellipsoid(mesh, (x+0.48,y+0.22,0.0), (0.23,0.22,0.21), fur, rings=7, sides=12)
    add_static_ellipsoid(mesh, (x+0.66,y+0.17,-0.01), (0.13,0.09,0.12), cream, rings=5, sides=9)
    add_static_ellipsoid(mesh, (x+0.76,y+0.18,-0.02), (0.035,0.028,0.028), black, rings=4, sides=7)
    add_static_ellipsoid(mesh, (x+0.49,y+0.27,-0.19), (0.025,0.022,0.017), (54,76,61), rings=4, sides=7)
    _triangle(mesh, (x+0.34,y+0.37,-0.04), (x+0.40,y+0.66,-0.04), (x+0.52,y+0.39,-0.04), dark)
    _triangle(mesh, (x+0.52,y+0.39,-0.04), (x+0.66,y+0.64,-0.04), (x+0.70,y+0.34,-0.04), dark)

    for lx,lz in ((x+0.28,-0.14),(x+0.39,0.14),(x-0.28,-0.14),(x-0.17,0.14)):
        add_static_tube(mesh, (lx,y-0.18,lz), (lx,-1.65,lz), 0.075,0.045,fur,sides=8)
        add_static_ellipsoid(mesh, (lx+0.05,-1.72,lz), (0.10,0.055,0.08), cream, rings=4, sides=8)

    # Long raised tail.
    add_static_tube(mesh, (x-0.48,y+0.08,0.03), (x-0.78,y+0.34,0.03), 0.055,0.045,fur,sides=8)
    add_static_tube(mesh, (x-0.78,y+0.34,0.03), (x-0.72,y+0.75,0.03), 0.045,0.025,dark,sides=8)
    mesh.validate()
    return mesh


def build_horse_mesh(*, x: float = 0.0, y: float = -0.92) -> Mesh:
    mesh = Mesh()
    coat = (151, 99, 61)
    dark = (70, 46, 35)
    cream = (205, 178, 145)
    black = (27, 25, 23)

    add_static_ellipsoid(mesh, (x,y,0.0), (0.72,0.34,0.30), coat, rings=8, sides=14)
    add_static_tube(mesh, (x+0.48,y+0.14,0.0), (x+0.70,y+0.72,0.0), 0.20,0.14,coat,sides=10)
    add_static_ellipsoid(mesh, (x+0.80,y+0.86,0.0), (0.28,0.18,0.20), coat, rings=7, sides=12)
    add_static_ellipsoid(mesh, (x+1.02,y+0.81,-0.01), (0.22,0.12,0.15), cream, rings=5, sides=10)
    add_static_ellipsoid(mesh, (x+0.90,y+0.93,-0.18), (0.028,0.025,0.018), black, rings=4, sides=7)
    _triangle(mesh, (x+0.70,y+1.00,-0.03), (x+0.72,y+1.25,-0.03), (x+0.82,y+1.03,-0.03), dark)
    _triangle(mesh, (x+0.84,y+1.02,-0.03), (x+0.93,y+1.23,-0.03), (x+0.97,y+0.98,-0.03), dark)

    for lx,lz in ((x+0.46,-0.18),(x+0.54,0.18),(x-0.45,-0.18),(x-0.35,0.18)):
        add_static_tube(mesh, (lx,y-0.24,lz), (lx,-1.62,lz), 0.09,0.055,coat,sides=8)
        add_static_ellipsoid(mesh, (lx+0.03,-1.70,lz), (0.12,0.07,0.10), dark, rings=4, sides=8)

    add_static_tube(mesh, (x-0.67,y+0.08,0.03), (x-1.00,y-0.20,0.03), 0.075,0.04,dark,sides=8)
    mesh.validate()
    return mesh


def build_car_mesh(*, x: float = 0.0, y: float = -1.22) -> Mesh:
    mesh = Mesh()
    body = (69, 105, 151)
    glass = (112, 145, 164)
    dark = (35, 38, 42)
    silver = (166, 171, 176)

    _box(mesh, (x,y,0.0), (0.74,0.22,0.30), body)
    _box(mesh, (x+0.05,y+0.34,0.0), (0.40,0.18,0.26), glass)
    _box(mesh, (x+0.69,y+0.04,-0.02), (0.10,0.10,0.26), silver)

    for wx in (x-0.45,x+0.45):
        # Front-side wheel sits slightly toward camera (negative Z).
        add_static_ellipsoid(mesh, (wx,y-0.23,-0.31), (0.17,0.17,0.07), dark, rings=7, sides=12)
        add_static_ellipsoid(mesh, (wx,y-0.23,-0.365), (0.075,0.075,0.025), silver, rings=5, sides=9)
    mesh.validate()
    return mesh


OBJECT_BUILDERS: dict[str, Callable[..., Mesh]] = {
    "dog": build_dog_mesh,
    "bird": build_bird_mesh,
    "cat": build_cat_mesh,
    "horse": build_horse_mesh,
    "car": build_car_mesh,
}


def supported_object_names() -> tuple[str, ...]:
    return ("human", *tuple(OBJECT_BUILDERS.keys()))


def _slots(count: int) -> list[float]:
    if count <= 1:
        return [0.0]
    width = min(3.0, 1.45 * (count - 1))
    left = -width * 0.5
    return [left + width * i / (count - 1) for i in range(count)]


def _translate(points: Iterable[Vec3], offset: Vec3) -> list[Vec3]:
    return [v_add(p, offset) for p in points]


def _merge_meshes(meshes: Sequence[Mesh]) -> Mesh:
    out = Mesh()
    for mesh in meshes:
        base = len(out.vertices)
        out.vertices.extend(mesh.vertices)
        out.faces.extend(Face(f.a+base, f.b+base, f.c+base, f.color) for f in mesh.faces)
    out.validate()
    return out


def _natural_pose(text: str) -> Pose:
    pose = pose_from_prompt(text)
    rotations = dict(pose.rotations)
    if not re.search(r"腕|手を上|手を振|arm|wave|waving|walk|歩", text, re.I):
        rotations.setdefault("l_shoulder", (0.0,0.0,-82.0))
        rotations.setdefault("r_shoulder", (0.0,0.0,82.0))
    return Pose(rotations)


def build_scene_geometry(plan: ScenePlan, prompt: str) -> tuple[Mesh, list[Vec3], tuple[str, ...], dict]:
    names = [name for name in plan.required_objects if name in supported_object_names()]
    xs = _slots(len(names))
    meshes: list[Mesh] = []
    positions: list[list[Vec3]] = []
    generated: list[str] = []
    details: dict = {}

    for name, x in zip(names, xs):
        if name == "human":
            sk = default_human_skeleton()
            mesh = build_human_mesh(sk)
            pose = _natural_pose(prompt)
            pts = _translate(skinned_positions(mesh, sk, pose), (x,0.0,0.0))
            meshes.append(mesh)
            positions.append(pts)
            generated.append(name)
            details[name] = {
                "geometry": "human-lbs",
                "bones": len(sk.bones),
                "pose_bones": sorted(pose.rotations),
                "offset": (x,0.0,0.0),
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
            }
            continue

        builder = OBJECT_BUILDERS[name]
        # Scene builders share x placement; their vertical defaults are tuned
        # per object category.
        mesh = builder(x=x)
        meshes.append(mesh)
        positions.append([v.bind_position for v in mesh.vertices])
        generated.append(name)
        details[name] = {
            "geometry": f"native-{name}",
            "offset_x": x,
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces),
        }

    ground = Mesh()
    add_static_quad(
        ground,
        (-2.8,-1.84,-0.95),
        (2.8,-1.84,-0.95),
        (2.8,-1.84,1.15),
        (-2.8,-1.84,1.15),
        (204,207,203),
    )
    meshes.append(ground)
    positions.append([v.bind_position for v in ground.vertices])

    merged = _merge_meshes(meshes)
    flat = [p for block in positions for p in block]
    return merged, flat, tuple(generated), details
