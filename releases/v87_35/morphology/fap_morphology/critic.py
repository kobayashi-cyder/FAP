from __future__ import annotations

from fap_media_generation import Critique, CritiqueIssue
from fap_scene_graph2 import SceneGraph2QualityCritic

from .pattern import parse_morphology_graph


class MorphologyQualityCritic:
    def __init__(self):
        self.base = SceneGraph2QualityCritic()

    def critique(self, request, artifact):
        base = self.base.critique(request, artifact)
        graph = parse_morphology_graph(request.prompt, request.constraints)
        generated = {
            str(row.get("node_id")): row
            for row in artifact.metadata.get("generated_nodes", [])
            if isinstance(row, dict)
        }

        issues = list(base.issues)
        morphology_score = 1.0
        failures = []
        for node in graph.nodes:
            if node.kind != "cat":
                continue
            attrs = node.attr_dict()
            row = generated.get(node.node_id, {})
            coat = attrs.get("coat_pattern")
            face = attrs.get("face_pattern")
            if coat and row.get("coat_pattern_applied") != coat:
                morphology_score = 0.0
                failures.append(f"{node.node_id}:coat={coat}")
            if face and row.get("face_pattern_applied") != face:
                morphology_score = 0.0
                failures.append(f"{node.node_id}:face={face}")

        if failures:
            issues.append(CritiqueIssue(
                "cat_pattern_unmet",
                "cat morphology/pattern not applied: " + ", ".join(failures),
                "fatal",
                "Apply the requested cat coat/face pattern before accepting.",
            ))

        score = min(float(base.score), morphology_score)
        evidence = dict(base.evidence)
        evidence.update({
            "kind": "morphology-quality",
            "morphology_score": morphology_score,
            "pattern_failures": failures,
        })
        return Critique(score, tuple(issues), evidence=evidence)
