from __future__ import annotations

from collections import Counter
from fap_media_generation import Critique, CritiqueIssue

from .graph import parse_scene_graph


class SceneGraph2QualityCritic:
    def critique(self, request, artifact):
        meta = dict(artifact.metadata)
        graph = parse_scene_graph(request.prompt, request.constraints)
        issues = []

        required_counts = graph.required_counts
        generated_counts = {
            str(k): int(v) for k, v in dict(meta.get("generated_counts", {})).items()
        }
        count_score = 1.0
        count_mismatches = {}
        for kind, required in required_counts.items():
            actual = generated_counts.get(kind, 0)
            if actual != required:
                count_score = 0.0
                count_mismatches[kind] = {"required": required, "actual": actual}
        if count_mismatches:
            issues.append(CritiqueIssue(
                "object_count_mismatch",
                f"required/generated counts differ: {count_mismatches}",
                "fatal",
                "Generate the exact requested count for every scene object.",
            ))

        forbidden_present = sorted(
            kind for kind in graph.forbidden_kinds if generated_counts.get(kind, 0) > 0
        )
        negative_score = 0.0 if forbidden_present else 1.0
        if forbidden_present:
            issues.append(CritiqueIssue(
                "forbidden_object_present",
                "forbidden object(s) were generated: " + ", ".join(forbidden_present),
                "fatal",
                "Remove all explicitly forbidden scene objects.",
            ))

        generated_nodes = {
            str(row.get("node_id")): row
            for row in meta.get("generated_nodes", [])
            if isinstance(row, dict)
        }
        attribute_score = 1.0
        state_score = 1.0
        attr_failures = []
        state_failures = []
        for node in graph.nodes:
            row = generated_nodes.get(node.node_id)
            if not row:
                attribute_score = state_score = 0.0
                continue
            expected_attrs = node.attr_dict()
            actual_attrs = dict(row.get("attributes", {}))
            if any(actual_attrs.get(k) != v for k, v in expected_attrs.items()):
                attribute_score = 0.0
                attr_failures.append(node.node_id)
            if node.state != "default" and not bool(row.get("state_applied", False)):
                state_score = 0.0
                state_failures.append(node.node_id)

        if attr_failures:
            issues.append(CritiqueIssue(
                "attribute_constraint_unmet",
                "requested attributes were not applied to: " + ", ".join(attr_failures),
                "fatal",
                "Apply requested object attributes before accepting.",
            ))
        if state_failures:
            issues.append(CritiqueIssue(
                "state_constraint_unmet",
                "requested pose/state is not implemented for: " + ", ".join(state_failures),
                "fatal",
                "Implement and apply the requested object state.",
            ))

        required_relations = {r.key() for r in graph.relations}
        applied_relations = set(str(x) for x in meta.get("applied_relations", ()))
        missing_relations = sorted(required_relations - applied_relations)
        relation_score = 0.0 if missing_relations else 1.0
        if missing_relations:
            issues.append(CritiqueIssue(
                "relation_constraint_unmet",
                "scene relation(s) were not applied: " + ", ".join(missing_relations),
                "fatal",
                "Apply all requested spatial/semantic relations.",
            ))

        viewpoint_score = (
            1.0 if str(meta.get("applied_viewpoint", "")) == graph.viewpoint else 0.0
        )
        if viewpoint_score == 0.0:
            issues.append(CritiqueIssue(
                "viewpoint_constraint_unmet",
                f"requested viewpoint={graph.viewpoint}",
                "fatal",
                "Render from the requested camera viewpoint.",
            ))

        layout_score = 1.0
        if graph.centered_subjects and "centered_subjects" not in set(meta.get("applied_constraints", ())):
            layout_score = 0.0
            issues.append(CritiqueIssue(
                "center_constraint_unmet",
                "centered-subject constraint was not applied",
                "fatal",
                "Center the requested scene.",
            ))

        styles = set(graph.requested_styles)
        style_score = 1.0
        if "photorealistic" in styles and not bool(meta.get("photorealistic_verified", False)):
            style_score = float(meta.get("photo_look_capability", 0.0))
            issues.append(CritiqueIssue(
                "photorealism_not_yet_verified",
                f"photo style requested; native capability={style_score:.2f}",
                "fatal",
                "Use a verified learned photo refiner before accepting photorealistic output.",
            ))
        if "illustration" in styles and not bool(meta.get("illustration_verified", False)):
            style_score = 0.0
            issues.append(CritiqueIssue(
                "illustration_style_unavailable",
                "illustration/anime style was requested but the active renderer is photo-look-native",
                "fatal",
                "Route to a verified illustration renderer instead of falsely accepting photo-look output.",
            ))

        score = min(
            count_score, negative_score, attribute_score, state_score,
            relation_score, viewpoint_score, layout_score, style_score,
        )
        return Critique(
            score,
            tuple(issues),
            evidence={
                "kind": "scene-graph2-quality",
                "score": score,
                "count_score": count_score,
                "negative_score": negative_score,
                "attribute_score": attribute_score,
                "state_score": state_score,
                "relation_score": relation_score,
                "viewpoint_score": viewpoint_score,
                "layout_score": layout_score,
                "style_score": style_score,
                "required_counts": required_counts,
                "generated_counts": generated_counts,
                "forbidden_kinds": list(graph.forbidden_kinds),
                "forbidden_present": forbidden_present,
                "required_relations": sorted(required_relations),
                "applied_relations": sorted(applied_relations),
                "requested_viewpoint": graph.viewpoint,
                "applied_viewpoint": meta.get("applied_viewpoint", ""),
                "requested_styles": sorted(styles),
            },
        )
