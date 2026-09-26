from __future__ import annotations

from typing import Callable, Optional

from .adaptive import AdaptiveCircuitController, SparseCreativityAdapter
from .local_adaptation_bridge import LocalAdaptationCircuitBridge


class UnifiedAdaptiveResponder:
    """Run only the V82 specialists selected by the shared sparse router."""

    def __init__(
        self,
        base_responder: Callable[[str, str, str], str],
        *,
        sparse_creativity: SparseCreativityAdapter,
        local_adaptation: LocalAdaptationCircuitBridge,
        top_k: int = 2,
    ):
        if not callable(base_responder):
            raise TypeError("base_responder must be callable")
        self.base_responder = base_responder
        self.sparse_creativity = sparse_creativity
        self.local_adaptation = local_adaptation
        self.top_k = max(1, int(top_k))

    def __call__(self, user_text: str, context: str, mode: str) -> str:
        routing_text = (str(user_text) + " " + str(context)).strip()
        candidates = self.sparse_creativity.generate(user_text, context, count=self.top_k)
        local_guidance = self.local_adaptation.guidance_if_routed(routing_text, top_k=self.top_k)

        lines = [context.rstrip()]
        if local_guidance:
            lines.append(local_guidance)
        if candidates:
            lines.extend([
                "[FAP V82 sparse creativity guidance]",
                "Verifier-approved hypotheses; not facts.",
            ])
            lines.extend(f"{c.operator}: {c.text}" for c in candidates)
            lines.append(self.sparse_creativity.base.recombine(candidates))
        augmented = "\n".join(x for x in lines if x)

        output = str(self.base_responder(user_text, augmented, mode)).strip()
        if not output:
            raise ValueError("base responder returned empty text")
        return output


def build_v82_responder(
    base_responder: Callable[[str, str, str], str],
    *,
    creativity_engine=None,
    local_core=None,
    controller: Optional[AdaptiveCircuitController] = None,
    top_k: int = 2,
):
    """Compose V82 over V81 local adaptation, V79 creativity and V78 learned guidance.

    V82 does not call the always-on V81/V79 wrappers. Instead it exposes V81 local
    adaptation and V79 creativity as verifier-approved specialists in one shared router.
    V78 teacher-learning guidance remains the lower responder layer.
    """
    if not callable(base_responder):
        raise TypeError("base_responder must be callable")

    from fap_creativity import CreativityEngine
    from fap_local_adaptation import LocalAdaptiveCore
    from fap_teacher_learning import TeacherLearningResponder

    shared = controller or AdaptiveCircuitController(top_k=top_k)
    engine = creativity_engine or CreativityEngine()
    sparse = SparseCreativityAdapter(engine, controller=shared, top_k=top_k)
    local = LocalAdaptationCircuitBridge(
        local_core or LocalAdaptiveCore(),
        controller=shared,
        top_k=top_k,
    )
    local.register()

    learned = TeacherLearningResponder()
    learned_base = learned.wrap(base_responder)
    return UnifiedAdaptiveResponder(
        learned_base,
        sparse_creativity=sparse,
        local_adaptation=local,
        top_k=top_k,
    )
