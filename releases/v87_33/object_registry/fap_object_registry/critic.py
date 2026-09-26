from __future__ import annotations

from fap_media_generation import Critique, CritiqueIssue
from .registry import parse_scene_plan


class ObjectRegistryQualityCritic:
    def critique(self, request, artifact):
        meta = dict(artifact.metadata)
        plan = parse_scene_plan(request.prompt, request.constraints)
        required = set(plan.required_objects)
        generated = set(str(x) for x in meta.get("generated_objects", ()))
        missing = sorted(required - generated)
        issues = []

        object_score = 1.0 if not missing else 0.0
        if missing:
            issues.append(CritiqueIssue(
                "missing_required_object",
                "required scene object(s) were not generated: " + ", ".join(missing),
                "fatal",
                "Generate every required object before accepting the scene.",
            ))

        layout_score = 1.0
        if plan.centered_subjects:
            applied = set(str(x) for x in meta.get("applied_constraints", ()))
            if "centered_subjects" not in applied:
                layout_score = 0.0
                issues.append(CritiqueIssue(
                    "center_constraint_unmet",
                    "centered-subject constraint was not confirmed",
                    "fatal",
                    "Center the generated subjects.",
                ))

        styles = set(plan.requested_styles)
        style_score = 1.0
        if "photorealistic" in styles:
            if bool(meta.get("photorealistic_verified", False)):
                style_score = 1.0
            else:
                style_score = float(meta.get("photo_look_capability", 0.0))
                issues.append(CritiqueIssue(
                    "photorealism_not_yet_verified",
                    f"photo style requested; current native photo-look capability={style_score:.2f}",
                    "fatal",
                    "Use a verified learned photo refiner before accepting photorealistic output.",
                ))

        score = min(object_score, layout_score, style_score)
        return Critique(
            score,
            tuple(issues),
            evidence={
                "kind": "object-registry-quality",
                "score": score,
                "object_score": object_score,
                "layout_score": layout_score,
                "style_score": style_score,
                "photo_look_capability": float(meta.get("photo_look_capability", 0.0)),
                "photorealistic_verified": bool(meta.get("photorealistic_verified", False)),
                "required_objects": sorted(required),
                "generated_objects": sorted(generated),
                "missing_objects": missing,
                "requested_styles": sorted(styles),
                "render_style": meta.get("render_style", ""),
                "photo_look_features": list(meta.get("photo_look_features", [])),
            },
        )
