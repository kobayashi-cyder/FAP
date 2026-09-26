from __future__ import annotations

from fap_media_generation import Critique, CritiqueIssue
from fap_scene_image.scene import parse_scene_plan


class PhotoLookQualityCritic:
    """Prompt/style gate for the V87.32 appearance layer.

    The native photo-look renderer earns partial style capability evidence, but
    a photorealistic request remains rejected until a learned/verified renderer
    actually reaches that capability.
    """

    def critique(self, request, artifact):
        metadata = dict(artifact.metadata)
        plan = parse_scene_plan(request.prompt, request.constraints)

        generated = set(str(x) for x in metadata.get("generated_objects", ()))
        required = set(plan.required_objects)
        missing = sorted(required - generated)
        unsupported = sorted(set(plan.unsupported_objects))
        issues = []

        object_score = 1.0 if not missing else 0.0
        if missing:
            issues.append(CritiqueIssue(
                "missing_required_object",
                "required scene object(s) were not generated: " + ", ".join(missing),
                "fatal",
                "Generate every required scene object before accepting the artifact.",
            ))
        if unsupported:
            issues.append(CritiqueIssue(
                "unsupported_scene_object",
                "current native scene engine does not support: " + ", ".join(unsupported),
                "fatal",
                "Add a native geometry/generation module for the unsupported object.",
            ))

        layout_score = 1.0
        if plan.centered_subjects:
            applied = set(str(x) for x in metadata.get("applied_constraints", ()))
            if "centered_subjects" not in applied:
                layout_score = 0.0
                issues.append(CritiqueIssue(
                    "center_constraint_unmet",
                    "the request requires centered subjects but the renderer did not confirm centered composition",
                    "fatal",
                    "Center the scene subjects.",
                ))

        requested_styles = set(plan.requested_styles)
        render_style = str(metadata.get("render_style", ""))
        photo_capability = float(metadata.get("photo_look_capability", 0.0))
        photoreal_verified = bool(metadata.get("photorealistic_verified", False))
        style_score = 1.0

        if "photorealistic" in requested_styles:
            if photoreal_verified and render_style == "photorealistic":
                style_score = 1.0
            else:
                style_score = max(0.0, min(0.95, photo_capability))
                issues.append(CritiqueIssue(
                    "photorealism_not_yet_verified",
                    (
                        "photo-style output was requested. V87.32 improves lighting/material/"
                        f"surface appearance (capability={style_score:.2f}) but is not a verified "
                        "photorealistic learned renderer."
                    ),
                    "fatal",
                    "Run the scene through a verified learned photo refiner before accepting a photorealistic request.",
                ))
        elif "illustration" in requested_styles and render_style not in {"illustration", "procedural-2d"}:
            style_score = 0.55
            issues.append(CritiqueIssue(
                "illustration_style_mismatch",
                f"illustration style was requested but the active renderer is {render_style or 'unknown'}",
                "high",
                "Use an illustration-capable renderer.",
            ))

        score = min(object_score, layout_score, style_score)
        return Critique(
            score,
            tuple(issues),
            evidence={
                "kind": "photo-look-quality",
                "score": score,
                "object_score": object_score,
                "layout_score": layout_score,
                "style_score": style_score,
                "photo_look_capability": photo_capability,
                "photorealistic_verified": photoreal_verified,
                "required_objects": sorted(required),
                "generated_objects": sorted(generated),
                "missing_objects": missing,
                "unsupported_objects": unsupported,
                "requested_styles": sorted(requested_styles),
                "render_style": render_style,
                "photo_look_features": list(metadata.get("photo_look_features", [])),
            },
        )
