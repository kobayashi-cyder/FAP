from __future__ import annotations

from dataclasses import replace
import math
import re

from fap_human_lbs.core import Face, Mesh
from fap_scene_graph2 import SceneGraph2, SceneNode, parse_scene_graph


def parse_morphology_graph(prompt: str, constraints=()) -> SceneGraph2:
    graph = parse_scene_graph(prompt, constraints)
    text = graph.source_text
    coat = None
    face_pattern = None
    if re.search(r"三毛|calico", text, re.I):
        coat = "calico"
    elif re.search(r"キジトラ|tabby", text, re.I):
        coat = "tabby"
    elif re.search(r"サバトラ", text, re.I):
        coat = "silver_tabby"
    elif re.search(r"茶トラ|orange tabby", text, re.I):
        coat = "orange_tabby"
    elif re.search(r"サビ|tortoiseshell", text, re.I):
        coat = "tortoiseshell"
    if re.search(r"八割れ|ハチワレ|hachiware|bicolor face", text, re.I):
        face_pattern = "hachiware"

    nodes = []
    for node in graph.nodes:
        if node.kind != "cat":
            nodes.append(node)
            continue
        attrs = dict(node.attributes)
        if coat:
            attrs["coat_pattern"] = coat
        if face_pattern:
            attrs["face_pattern"] = face_pattern
        nodes.append(replace(node, attributes=tuple(sorted(attrs.items()))))
    return replace(graph, nodes=tuple(nodes))


def _centroid(mesh: Mesh, face: Face):
    pts = [mesh.vertices[i].bind_position for i in (face.a, face.b, face.c)]
    return (
        sum(p[0] for p in pts) / 3.0,
        sum(p[1] for p in pts) / 3.0,
        sum(p[2] for p in pts) / 3.0,
    )


def _noise(x: float, y: float, z: float) -> float:
    return math.sin(x * 4.31 + math.sin(y * 2.17) * 1.9 + z * 3.73)


def apply_cat_pattern(mesh: Mesh, attrs: dict[str, str]) -> tuple[Mesh, dict]:
    coat = attrs.get("coat_pattern")
    face_pattern = attrs.get("face_pattern")
    if not coat and not face_pattern:
        return mesh, {"coat_pattern_applied": None, "face_pattern_applied": None}

    out = Mesh(vertices=list(mesh.vertices), faces=[])
    for face in mesh.faces:
        x, y, z = _centroid(mesh, face)
        color = face.color

        # Preserve very dark eye/nose geometry.
        if sum(color) > 120:
            if coat == "calico":
                # Broad low-frequency patches: white base, black/orange islands.
                n1 = _noise(x * 0.75, y * 0.65, z * 0.7)
                n2 = _noise(x * 0.52 + 1.2, y * 0.80, z * 0.55 - 0.7)
                if n1 > 0.38:
                    color = (48, 45, 42)
                elif n2 > 0.28:
                    color = (195, 109, 46)
                else:
                    color = (232, 228, 216)
            elif coat == "tabby":
                stripe = math.sin((x * 12.0) + y * 7.0)
                color = (70, 63, 55) if stripe > 0.45 else (148, 132, 110)
            elif coat == "silver_tabby":
                stripe = math.sin((x * 12.0) + y * 7.0)
                color = (63, 67, 70) if stripe > 0.45 else (184, 186, 184)
            elif coat == "orange_tabby":
                stripe = math.sin((x * 12.0) + y * 7.0)
                color = (154, 74, 28) if stripe > 0.45 else (222, 137, 67)
            elif coat == "tortoiseshell":
                n = _noise(x * 0.9, y * 0.85, z * 0.8)
                color = (45, 42, 39) if n > 0 else (180, 82, 34)

            if face_pattern == "hachiware":
                # Cat head center is roughly x=+0.48,y=-0.86 in the native cat.
                # Front side is negative Z. A widening V-shaped white blaze is
                # carved from forehead toward muzzle.
                on_head = x > 0.22 and y > -1.08 and z < -0.08
                if on_head:
                    forehead_y = max(0.0, min(1.0, (y + 1.08) / 0.52))
                    half_width = 0.035 + (1.0 - forehead_y) * 0.16
                    if abs(x - 0.49) < half_width:
                        color = (238, 235, 225)

        out.faces.append(Face(face.a, face.b, face.c, color))
    out.validate()
    return out, {
        "coat_pattern_applied": coat,
        "face_pattern_applied": face_pattern,
    }
