from __future__ import annotations

from fap_media_generation import Critique, CritiqueIssue

from .dna import COMPLEMENT, parse_dna_request


class ScientificGeometryCritic:
    def critique(self, request, artifact):
        expected = parse_dna_request(request.prompt, request.constraints)
        actual = dict(artifact.metadata.get("scientific_geometry", {}))
        issues = []

        object_score = 1.0 if "dna" in set(artifact.metadata.get("generated_objects", ())) else 0.0
        if object_score == 0.0:
            issues.append(CritiqueIssue(
                "dna_missing",
                "DNA geometry was requested but no DNA object was generated.",
                "fatal",
                "Generate a DNA object.",
            ))

        count_score = 1.0 if int(actual.get("base_pairs", -1)) == expected.base_pairs else 0.0
        if count_score == 0.0:
            issues.append(CritiqueIssue(
                "base_pair_count_mismatch",
                f"expected {expected.base_pairs} bp, got {actual.get('base_pairs')}",
                "fatal",
                "Generate the exact requested base-pair count.",
            ))

        sequence_score = 1.0
        if str(actual.get("sequence", "")) != expected.sequence:
            sequence_score = 0.0
        comp = str(actual.get("complement", ""))
        if len(comp) != len(expected.sequence) or any(
            COMPLEMENT[a] != b for a, b in zip(expected.sequence, comp)
        ):
            sequence_score = 0.0
        if sequence_score == 0.0:
            issues.append(CritiqueIssue(
                "dna_complementarity_mismatch",
                "sequence/complement metadata is not Watson-Crick complementary.",
                "fatal",
                "Preserve exact sequence and complementary base pairing.",
            ))

        form_score = 1.0
        if expected.form != "B-DNA":
            form_score = 0.0
            issues.append(CritiqueIssue(
                "dna_form_unverified",
                f"{expected.form} was requested; V87.36 verification is currently calibrated for B-DNA.",
                "fatal",
                "Use B-DNA or add form-specific verification before accepting.",
            ))
        elif str(actual.get("form", "")) != "B-DNA":
            form_score = 0.0

        handedness_score = 1.0 if actual.get("handedness") == expected.handedness else 0.0
        geometry_score = 1.0
        checks = (
            ("diameter_nm", expected.diameter_nm, 0.05),
            ("rise_nm", expected.rise_nm, 0.01),
            ("bp_per_turn", expected.bp_per_turn, 0.15),
            ("pitch_nm", expected.pitch_nm, 0.08),
        )
        for key, target, tolerance in checks:
            try:
                value = float(actual.get(key))
            except Exception:
                geometry_score = 0.0
                continue
            if abs(value - target) > tolerance:
                geometry_score = 0.0
        if geometry_score == 0.0:
            issues.append(CritiqueIssue(
                "dna_geometry_parameter_mismatch",
                "DNA helix parameters are outside the verified tolerance.",
                "fatal",
                "Use the requested/verified DNA form parameters.",
            ))

        strand_score = 1.0 if (
            int(actual.get("backbone_strands", 0)) == 2
            and bool(actual.get("antiparallel", False))
        ) else 0.0
        if strand_score == 0.0:
            issues.append(CritiqueIssue(
                "dna_strand_structure_mismatch",
                "DNA must contain two antiparallel backbone strands.",
                "fatal",
                "Generate two antiparallel strands.",
            ))

        score = min(
            object_score,
            count_score,
            sequence_score,
            form_score,
            handedness_score,
            geometry_score,
            strand_score,
        )
        return Critique(
            score,
            tuple(issues),
            evidence={
                "kind": "scientific-geometry",
                "score": score,
                "object_score": object_score,
                "count_score": count_score,
                "sequence_score": sequence_score,
                "form_score": form_score,
                "handedness_score": handedness_score,
                "geometry_score": geometry_score,
                "strand_score": strand_score,
                "base_pairs": actual.get("base_pairs"),
                "sequence": actual.get("sequence"),
                "complement": actual.get("complement"),
                "form": actual.get("form"),
                "handedness": actual.get("handedness"),
                "diameter_nm": actual.get("diameter_nm"),
                "rise_nm": actual.get("rise_nm"),
                "bp_per_turn": actual.get("bp_per_turn"),
                "pitch_nm": actual.get("pitch_nm"),
            },
        )
