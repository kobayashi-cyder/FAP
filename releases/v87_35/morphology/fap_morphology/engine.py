from __future__ import annotations

from collections import Counter
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from fap_human_lbs.core import Face, Mesh, v_add
from fap_media_generation import GenerationRequest, MediaArtifact
from fap_object_registry.registry import OBJECT_BUILDERS, supported_object_names
from fap_photo_look import PhotoLookEngine, render_photo_look_png
from fap_scene_graph2.engine import (
    _human_mesh_and_positions,
    _merge,
    _node_centers,
    _view_angles,
)
from fap_scene_image.scene import add_static_quad

from .pattern import apply_cat_pattern, parse_morphology_graph


class MorphologyEngine:
    def __init__(self, *, artifact_dir: str | Path):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.engine_id = "fap-morphology-v1"
        self.fallback = PhotoLookEngine(artifact_dir=self.artifact_dir)

    def probe(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "model_id": "fap-morphology-v1",
            "offline": True,
            "external_weights": False,
            "external_runtime": False,
            "stdlib_only": True,
            "supported_scene_objects": list(supported_object_names()),
            "cat_patterns": [
                "calico",
                "hachiware",
                "tabby",
                "silver_tabby",
                "orange_tabby",
                "tortoiseshell",
            ],
            "render_style": "photo-look-native",
            "photo_look_capability": 0.58,
            "photorealistic_verified": False,
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        graph = parse_morphology_graph(prompt, request.constraints)
        if not graph.nodes:
            fallback = self.fallback.generate(
                request, prompt=prompt, previous=previous, critique=critique
            )
            meta = dict(fallback.metadata)
            meta["engine_id"] = self.engine_id
            return replace(fallback, metadata=meta)

        centers = _node_centers(graph)
        meshes: list[Mesh] = []
        positions: list[list[tuple[float, float, float]]] = []
        node_results: list[dict] = []

        for node in graph.nodes:
            center = tuple(centers[node.node_id])
            attrs = node.attr_dict()
            if node.kind == "human":
                mesh, pts, details = _human_mesh_and_positions(
                    node, center, graph.source_text
                )
                pattern_meta = {}
            else:
                mesh = OBJECT_BUILDERS[node.kind](x=0.0)
                pattern_meta = {}
                if node.kind == "cat":
                    mesh, pattern_meta = apply_cat_pattern(mesh, attrs)
                pts = [v_add(v.bind_position, center) for v in mesh.vertices]
                details = {
                    "state_applied": (
                        node.state == "default"
                        or (node.kind in {"dog", "cat", "horse"} and node.state == "standing")
                        or (node.kind == "bird" and node.state in {"flying", "perched"})
                        or (node.kind == "car" and node.state in {"moving", "parked"})
                    )
                }

            meshes.append(mesh)
            positions.append(pts)
            node_results.append({
                "node_id": node.node_id,
                "kind": node.kind,
                "attributes": attrs,
                "state": node.state,
                "state_applied": bool(details["state_applied"]),
                "center": list(center),
                **pattern_meta,
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
                "adapter": "fap-morphology",
                "model_id": "fap-morphology-v1",
                "offline": True,
                "external_weights": False,
                "stdlib_only": True,
                "generated_objects": generated_kinds,
                "generated_counts": generated_counts,
                "generated_nodes": node_results,
                "forbidden_kinds": list(graph.forbidden_kinds),
                "requested_relations": [r.key() for r in graph.relations],
                "applied_relations": applied_relations,
                "requested_styles": list(graph.requested_styles),
                "render_style": "photo-look-native",
                "photo_look_capability": 0.58,
                "photorealistic_verified": False,
                "illustration_verified": False,
                "requested_viewpoint": graph.viewpoint,
                "applied_viewpoint": graph.viewpoint,
                "applied_constraints": applied_constraints,
                "photo_look_features": [k for k, v in features.items() if v],
                "morphology": {
                    "cat_patterns": [
                        {
                            "node_id": row["node_id"],
                            "coat_pattern": row.get("coat_pattern_applied"),
                            "face_pattern": row.get("face_pattern_applied"),
                        }
                        for row in node_results if row["kind"] == "cat"
                    ]
                },
            },
        )
