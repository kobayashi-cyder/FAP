from __future__ import annotations

from fap_media_generation import Critique, CritiqueIssue

from .scene import parse_scene_plan


class SceneQualityCritic:
    """Fail closed on required objects, layout constraints and style capability.

    This critic deliberately distinguishes structural prompt compliance from
    photorealistic visual quality. The current renderer can structurally build
    humans and dogs, but it must reject a requested photo-real style because
    V87.31 has no learned photorealistic renderer yet.
    """

    def critique(self, request, artifact):
        metadata = dict(artifact.metadata)
        plan = parse_scene_plan(request.prompt, request.constraints)

        generated = set(str(x) for x in metadata.get("generated_objects", ()))
        required = set(plan.required_objects)
        missing = sorted(required - generated)
        unsupported = sorted(set(plan.unsupported_objects))

        object_score = 1.0 if not missing else 0.0
        layout_score = 1.0
        issues = []

        if missing:
            issues.append(CritiqueIssue(
                "missing_required_object",
                "required scene object(s) were not generated: " + ", ".join(missing),
                "fatal",
                "Generate every required scene object before accepting the artifact.",
            ))

        if unsupported:
            # Unsupported required objects are necessarily included in missing,
            # but expose a separate issue so the user sees the capability gap.
            issues.append(CritiqueIssue(
                "unsupported_scene_object",
                "current native scene engine does not support: " + ", ".join(unsupported),
                "fatal",
                "Add a native geometry/generation module for the unsupported object.",
            ))

        if plan.centered_subjects:
            applied = set(str(x) for x in metadata.get("applied_constraints", ()))
            if "centered_subjects" not in applied:
                layout_score = 0.0
                issues.append(CritiqueIssue(
                    "center_constraint_unmet",
                    "the request requires centered subjects but the renderer did not confirm centered composition",
                    "fatal",
                    "Center the scene subjects and mark centered_subjects as applied.",
                ))

        requested_styles = set(plan.requested_styles)
        render_style = str(metadata.get("render_style", ""))
        style_score = 1.0

        if "photorealistic" in requested_styles and render_style != "photorealistic":
            style_score = 0.0
            issues.append(CritiqueIssue(
                "photorealistic_style_unavailable",
                f"photorealistic output was requested but the active renderer is {render_style or 'unknown'}",
                "fatal",
                "Use a renderer/model that can actually produce photorealistic output; do not report success from geometric output.",
            ))
        elif "illustration" in requested_styles and render_style not in {"illustration", "procedural-2d"}:
            style_score = 0.45
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
                "kind": "scene-quality",
                "score": score,
                "object_score": object_score,
                "layout_score": layout_score,
                "style_score": style_score,
                "required_objects": sorted(required),
                "generated_objects": sorted(generated),
                "missing_objects": missing,
                "unsupported_objects": unsupported,
                "requested_styles": sorted(requested_styles),
                "render_style": render_style,
            },
        )
