from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from collections import Counter

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
from fap_media_generation import GenerationRequest, MediaArtifact
from fap_object_registry.registry import OBJECT_BUILDERS, supported_object_names
from fap_photo_look import PhotoLookEngine, render_photo_look_png
from fap_scene_image.scene import add_static_quad

from .graph import SceneGraph2, SceneNode, parse_scene_graph


_COLOR_RGB = {
    "white": (232, 232, 224),
    "black": (45, 45, 43),
    "red": (176, 61, 55),
    "blue": (65, 105, 164),
    "brown": (139, 93, 62),
    "gray": (139, 143, 145),
}


def _slots(count: int) -> list[float]:
    if count <= 1:
        return [0.0]
    width = min(4.0, 1.20 * (count - 1))
    left = -width * 0.5
    return [left + width * i / (count - 1) for i in range(count)]


def _copy_mesh_with_color(mesh: Mesh, color_name: str | None) -> Mesh:
    if not color_name or color_name not in _COLOR_RGB:
        return mesh
    target = _COLOR_RGB[color_name]
    out = Mesh(vertices=list(mesh.vertices), faces=[])
    for face in mesh.faces:
        # Preserve eyes/nose/dark detail and warm beaks; recolor body surfaces.
        r, g, b = face.color
        preserve = (r + g + b < 150) or (r > 180 and g > 115 and b < 100)
        color = face.color if preserve else target
        out.faces.append(Face(face.a, face.b, face.c, color))
    out.validate()
    return out


def _merge(meshes: list[Mesh]) -> Mesh:
    out = Mesh()
    for mesh in meshes:
        base = len(out.vertices)
        out.vertices.extend(mesh.vertices)
        out.faces.extend(
            Face(f.a + base, f.b + base, f.c + base, f.color)
            for f in mesh.faces
        )
    out.validate()
    return out


def _view_angles(viewpoint: str) -> tuple[float, float]:
    return {
        "front": (0.0, -4.0),
        "side": (88.0, -3.0),
        "back": (178.0, -3.0),
        "oblique": (35.0, -5.0),
    }.get(viewpoint, (0.0, -4.0))


def _node_centers(graph: SceneGraph2) -> dict[str, list[float]]:
    centers: dict[str, list[float]] = {}
    xs = _slots(len(graph.nodes))
    for node, x in zip(graph.nodes, xs):
        y = 0.0
        if node.kind == "bird" and node.state == "flying":
            y += 0.85
        centers[node.node_id] = [x, y, 0.0]

    def nodes(kind: str):
        return [n for n in graph.nodes if n.kind == kind]

    for rel in graph.relations:
        srcs, tgts = nodes(rel.source_kind), nodes(rel.target_kind)
        if not srcs or not tgts:
            continue
        target = centers[tgts[0].node_id]
        if rel.relation == "above":
            for src in srcs:
                centers[src.node_id][1] = max(centers[src.node_id][1], target[1] + 1.00)
        elif rel.relation == "below":
            for src in srcs:
                centers[src.node_id][1] = min(centers[src.node_id][1], target[1] - 0.45)
        elif rel.relation == "left_of":
            for i, src in enumerate(srcs):
                centers[src.node_id][0] = target[0] - 1.15 - i * 0.55
        elif rel.relation == "right_of":
            for i, src in enumerate(srcs):
                centers[src.node_id][0] = target[0] + 1.15 + i * 0.55
        elif rel.relation == "next_to":
            for i, src in enumerate(srcs):
                centers[src.node_id][0] = target[0] + 1.05 + i * 0.55
        elif rel.relation == "looking_at":
            # Native animal primitives face +X. Place target to the right of
            # the source so the relation is visually meaningful.
            src = srcs[0]
            if centers[src.node_id][0] >= target[0]:
                centers[src.node_id][0] = target[0] - 1.10
    return centers


def _human_mesh_and_positions(node: SceneNode, center: tuple[float, float, float], text: str):
    sk = default_human_skeleton()
    mesh = build_human_mesh(sk)
    pose_text = text
    if node.state == "sitting":
        pose_text += " 座る"
    elif node.state == "walking":
        pose_text += " 歩く"
    elif node.state == "standing":
        pose_text += " 直立 腕を下げる"
    pose = pose_from_prompt(pose_text)
    pts = [v_add(p, center) for p in skinned_positions(mesh, sk, pose)]
    return mesh, pts, {
        "geometry": "human-lbs",
        "pose_bones": sorted(pose.rotations),
        "state_applied": node.state in {"default", "sitting", "walking", "standing"},
    }


def _static_mesh_and_positions(node: SceneNode, center: tuple[float, float, float]):
    builder = OBJECT_BUILDERS[node.kind]
    mesh = builder(x=0.0)
    color = node.attr_dict().get("color")
    mesh = _copy_mesh_with_color(mesh, color)
    pts = [v_add(v.bind_position, center) for v in mesh.vertices]
    state_applied = (
        node.state == "default"
        or (node.kind in {"dog", "cat", "horse"} and node.state == "standing")
        or (node.kind == "bird" and node.state in {"flying", "perched"})
        or (node.kind == "car" and node.state in {"moving", "parked"})
    )
    return mesh, pts, {
        "geometry": f"native-{node.kind}",
        "state_applied": state_applied,
    }


class SceneGraph2Engine:
    def __init__(self, *, artifact_dir: str | Path):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.engine_id = "fap-scene-graph2-v1"
        self.fallback = PhotoLookEngine(artifact_dir=self.artifact_dir)

    def probe(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "model_id": "fap-scene-graph2-v1",
            "offline": True,
            "external_weights": False,
            "external_runtime": False,
            "stdlib_only": True,
            "supported_scene_objects": list(supported_object_names()),
            "scene_graph2": True,
            "supports": [
                "count", "color", "state", "relations", "negative_constraints", "viewpoint"
            ],
            "render_style": "photo-look-native",
            "photo_look_capability": 0.58,
            "photorealistic_verified": False,
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        graph = parse_scene_graph(prompt, request.constraints)
        if not graph.nodes:
            fallback = self.fallback.generate(
                request, prompt=prompt, previous=previous, critique=critique
            )
            meta = dict(fallback.metadata)
            meta.update({
                "engine_id": self.engine_id,
                "adapter": "fap-scene-graph2-fallback",
                "scene_graph2": {
                    "required_counts": {},
                    "forbidden_kinds": list(graph.forbidden_kinds),
                    "relations": [r.key() for r in graph.relations],
                    "viewpoint": graph.viewpoint,
                },
            })
            return replace(fallback, metadata=meta)

        centers = _node_centers(graph)
        meshes: list[Mesh] = []
        positions: list[list[tuple[float, float, float]]] = []
        node_results: list[dict] = []

        for node in graph.nodes:
            center = tuple(centers[node.node_id])
            if node.kind == "human":
                mesh, pts, details = _human_mesh_and_positions(node, center, graph.source_text)
            else:
                mesh, pts, details = _static_mesh_and_positions(node, center)
            meshes.append(mesh)
            positions.append(pts)
            node_results.append({
                "node_id": node.node_id,
                "kind": node.kind,
                "attributes": node.attr_dict(),
                "state": node.state,
                "state_applied": bool(details["state_applied"]),
                "center": list(center),
            })

        ground = Mesh()
        add_static_quad(
            ground,
            (-3.4, -1.84, -1.10),
            (3.4, -1.84, -1.10),
            (3.4, -1.84, 1.25),
            (-3.4, -1.84, 1.25),
            (204, 207, 203),
        )
        meshes.append(ground)
        positions.append([v.bind_position for v in ground.vertices])

        merged = _merge(meshes)
        flat_positions = [p for block in positions for p in block]
        generated_kinds = [n.kind for n in graph.nodes]
        yaw, pitch = _view_angles(graph.viewpoint)
        data, features = render_photo_look_png(
            merged,
            flat_positions,
            generated_objects=generated_kinds,
            width=request.width,
            height=request.height,
            yaw_deg=yaw,
            pitch_deg=pitch,
        )

        digest = sha256(data).hexdigest()
        path = self.artifact_dir / f"{digest}.png"
        path.write_bytes(data)

        generated_counts = dict(Counter(generated_kinds))
        applied_relations = [
            rel.key()
            for rel in graph.relations
            if rel.source_kind in generated_counts and rel.target_kind in generated_counts
        ]
        applied_constraints = []
        if graph.centered_subjects:
            applied_constraints.append("centered_subjects")

        return MediaArtifact(
            media_type="image",
            digest=digest,
            mime_type="image/png",
            locator=str(path),
            metadata={
                "engine_id": self.engine_id,
                "adapter": "fap-scene-graph2",
                "model_id": "fap-scene-graph2-v1",
                "offline": True,
                "external_weights": False,
                "stdlib_only": True,
                "generated_objects": generated_kinds,
                "generated_counts": generated_counts,
                "forbidden_kinds": list(graph.forbidden_kinds),
                "generated_nodes": node_results,
                "requested_relations": [r.key() for r in graph.relations],
                "applied_relations": applied_relations,
                "requested_styles": list(graph.requested_styles),
                "render_style": "photo-look-native",
                "photo_look_capability": 0.58,
                "photorealistic_verified": False,
                "illustration_verified": False,
                "requested_viewpoint": graph.viewpoint,
                "applied_viewpoint": graph.viewpoint,
                "view_yaw_deg": yaw,
                "view_pitch_deg": pitch,
                "centered_subjects": graph.centered_subjects,
                "applied_constraints": applied_constraints,
                "photo_look_features": [k for k, enabled in features.items() if enabled],
                "scene_graph2": {
                    "required_counts": graph.required_counts,
                    "forbidden_kinds": list(graph.forbidden_kinds),
                    "relations": [r.key() for r in graph.relations],
                    "viewpoint": graph.viewpoint,
                    "nodes": node_results,
                },
            },
        )
