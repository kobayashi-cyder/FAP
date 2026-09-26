from __future__ import annotations

from .contracts import (
    Critique,
    GenerationRequest,
    GenerationResult,
    GenerationStep,
    MediaArtifact,
    MediaCritic,
    MediaGenerator,
)


class GenerationError(RuntimeError):
    pass


class BoundedMediaGenerationController:
    """Bounded generate -> critic -> repair -> regenerate controller.

    FAP does not pretend to contain a photorealistic image model or a video
    diffusion model here. Any connected backend must participate in a bounded,
    evidence-bearing refinement loop.
    """

    def __init__(self, generator: MediaGenerator, critic: MediaCritic):
        self.generator = generator
        self.critic = critic

    def run(self, request: GenerationRequest) -> GenerationResult:
        request.validate()
        prompt = request.prompt.strip()
        previous: MediaArtifact | None = None
        previous_critique: Critique | None = None
        best: MediaArtifact | None = None
        best_score = -1.0
        steps: list[GenerationStep] = []
        seen_digests: set[str] = set()

        for attempt in range(1, request.max_attempts + 1):
            artifact = self.generator.generate(
                request,
                prompt=prompt,
                previous=previous,
                critique=previous_critique,
            )
            artifact.validate()
            if artifact.media_type != request.media_type:
                raise GenerationError("generator returned wrong media type")

            critique = self.critic.critique(request, artifact)
            critique.validate()
            steps.append(GenerationStep(attempt, prompt, artifact, critique))

            if critique.score > best_score:
                best = artifact
                best_score = float(critique.score)

            if artifact.digest in seen_digests:
                return GenerationResult(
                    "exhausted",
                    best,
                    max(0.0, best_score),
                    tuple(steps),
                    "duplicate artifact detected; refinement stalled",
                )
            seen_digests.add(artifact.digest)

            if critique.score >= request.min_score and not critique.has_fatal:
                return GenerationResult(
                    "accepted",
                    artifact,
                    float(critique.score),
                    tuple(steps),
                    "quality gate satisfied",
                )

            if critique.has_fatal:
                return GenerationResult(
                    "rejected",
                    best,
                    max(0.0, best_score),
                    tuple(steps),
                    "critic reported fatal evidence",
                )

            previous = artifact
            previous_critique = critique
            prompt = self._repair_prompt(request, critique)

        return GenerationResult(
            "exhausted",
            best,
            max(0.0, best_score),
            tuple(steps),
            "attempt budget exhausted",
        )

    @staticmethod
    def _repair_prompt(request: GenerationRequest, critique: Critique) -> str:
        hints = []
        for issue in critique.issues:
            hint = issue.repair_hint.strip() or issue.detail.strip()
            if hint:
                hints.append(f"[{issue.code}] {hint}")
        parts = [request.prompt.strip()]
        if request.constraints:
            parts.append("Hard constraints: " + " | ".join(request.constraints))
        if hints:
            parts.append("Repair only these verified defects: " + " | ".join(hints[:12]))
        return "\n".join(parts)
