from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Sequence

from fap_human_lbs.core import Mesh
from fap_scene_image.scene import add_static_ellipsoid, add_static_tube


BASE_COLORS = {
    "A": (205, 70, 72),
    "T": (72, 116, 205),
    "G": (74, 160, 92),
    "C": (220, 183, 67),
}
COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}


@dataclass(frozen=True)
class DNARequest:
    form: str
    base_pairs: int
    sequence: str
    complement: str
    handedness: str
    diameter_nm: float
    rise_nm: float
    bp_per_turn: float
    viewpoint: str

    @property
    def pitch_nm(self) -> float:
        return self.rise_nm * self.bp_per_turn


def _extract_sequence(text: str) -> str:
    m = re.search(r"(?:配列|sequence)\s*[:：]?\s*([ATGCatgc]{2,200})", text, re.I)
    if m:
        return m.group(1).upper()
    # Also accept a bare DNA sequence if it is long enough not to be ordinary prose.
    m = re.search(r"\b([ATGCatgc]{6,200})\b", text)
    return m.group(1).upper() if m else ""


def _extract_count(text: str, sequence: str) -> int:
    m = re.search(r"(\d{1,3})\s*(?:塩基対|bp|base\s*pairs?)", text, re.I)
    if m:
        return max(2, min(120, int(m.group(1))))
    return len(sequence) if sequence else 20


def _viewpoint(text: str) -> str:
    if re.search(r"側面|横から|side view", text, re.I):
        return "side"
    if re.search(r"上から|top view|軸方向", text, re.I):
        return "top"
    if re.search(r"斜め|oblique|3/4", text, re.I):
        return "oblique"
    return "oblique"


def parse_dna_request(prompt: str, constraints: Sequence[str] = ()) -> DNARequest:
    text = "\n".join([str(prompt or ""), *(str(x or "") for x in constraints)])
    seq = _extract_sequence(text)
    count = _extract_count(text, seq)
    if not seq:
        seed = "ATGC"
        seq = "".join(seed[i % 4] for i in range(count))
    elif len(seq) < count:
        seq = (seq * ((count + len(seq) - 1) // len(seq)))[:count]
    else:
        seq = seq[:count]
    comp = "".join(COMPLEMENT[b] for b in seq)

    form = "B-DNA"
    if re.search(r"\bA[- ]?DNA\b", text, re.I):
        form = "A-DNA"
    elif re.search(r"\bZ[- ]?DNA\b", text, re.I):
        form = "Z-DNA"

    # V87.36 renders verified B-DNA only; other forms stay explicit in metadata
    # so the critic can fail closed rather than silently drawing the wrong helix.
    if form == "B-DNA":
        diameter_nm = 2.0
        rise_nm = 0.34
        bp_per_turn = 10.5
        handedness = "right"
    elif form == "A-DNA":
        diameter_nm = 2.3
        rise_nm = 0.26
        bp_per_turn = 11.0
        handedness = "right"
    else:
        diameter_nm = 1.8
        rise_nm = 0.37
        bp_per_turn = 12.0
        handedness = "left"

    return DNARequest(
        form=form,
        base_pairs=count,
        sequence=seq,
        complement=comp,
        handedness=handedness,
        diameter_nm=diameter_nm,
        rise_nm=rise_nm,
        bp_per_turn=bp_per_turn,
        viewpoint=_viewpoint(text),
    )


def reverse_complement(sequence: str) -> str:
    return "".join(COMPLEMENT[b] for b in reversed(sequence))


def build_dna_mesh(spec: DNARequest) -> tuple[Mesh, list[tuple[float, float, float]], dict]:
    mesh = Mesh()
    scale = 0.42  # render units per nm
    radius = (spec.diameter_nm * 0.5) * scale
    rise = spec.rise_nm * scale
    twist = (2.0 * math.pi) / spec.bp_per_turn

    backbone1 = []
    backbone2 = []
    pair_centers = []
    for i in range(spec.base_pairs):
        theta = i * twist
        y = (i - (spec.base_pairs - 1) * 0.5) * rise
        p1 = (radius * math.cos(theta), y, radius * math.sin(theta))
        p2 = (radius * math.cos(theta + math.pi), y, radius * math.sin(theta + math.pi))
        mid = (0.0, y, 0.0)
        backbone1.append(p1)
        backbone2.append(p2)
        pair_centers.append(mid)

        # Sugar/base anchor nodes and base-pair halves.
        add_static_ellipsoid(mesh, p1, (0.055, 0.055, 0.055), (210, 135, 54), rings=4, sides=7)
        add_static_ellipsoid(mesh, p2, (0.055, 0.055, 0.055), (210, 135, 54), rings=4, sides=7)
        add_static_tube(mesh, p1, mid, 0.033, 0.026, BASE_COLORS[spec.sequence[i]], sides=7)
        add_static_tube(mesh, p2, mid, 0.033, 0.026, BASE_COLORS[spec.complement[i]], sides=7)

    for a, b in zip(backbone1, backbone1[1:]):
        add_static_tube(mesh, a, b, 0.040, 0.040, (190, 126, 48), sides=8)
    for a, b in zip(backbone2, backbone2[1:]):
        add_static_tube(mesh, a, b, 0.040, 0.040, (190, 126, 48), sides=8)

    mesh.validate()
    positions = [v.bind_position for v in mesh.vertices]
    metadata = {
        "form": spec.form,
        "base_pairs": spec.base_pairs,
        "sequence": spec.sequence,
        "complement": spec.complement,
        "reverse_complement": reverse_complement(spec.sequence),
        "handedness": spec.handedness,
        "diameter_nm": spec.diameter_nm,
        "rise_nm": spec.rise_nm,
        "bp_per_turn": spec.bp_per_turn,
        "pitch_nm": spec.pitch_nm,
        "antiparallel": True,
        "backbone_strands": 2,
        "render_scale_units_per_nm": scale,
    }
    return mesh, positions, metadata


def view_angles(viewpoint: str) -> tuple[float, float]:
    if viewpoint == "side":
        return (0.0, 0.0)
    if viewpoint == "top":
        return (0.0, -88.0)
    return (28.0, -10.0)
