from __future__ import annotations

from typing import Callable, Optional

from .adaptive import AdaptiveCircuitController, AdaptiveCreativityResponder, SparseCreativityAdapter


def build_v82_responder(
    base_responder: Callable[[str, str, str], str],
    *,
    creativity_engine=None,
    controller: Optional[AdaptiveCircuitController] = None,
    top_k: int = 2,
):
    """Compose V82 sparse adaptive circuits in front of V78 learned guidance.

    Call order:
        user -> V82 sparse/verified creativity -> V78 learned guidance -> base responder
    """
    if not callable(base_responder):
        raise TypeError("base_responder must be callable")

    from fap_creativity import CreativityEngine
    from fap_teacher_learning import TeacherLearningResponder

    engine = creativity_engine or CreativityEngine()
    sparse = SparseCreativityAdapter(engine, controller=controller, top_k=top_k)
    learned = TeacherLearningResponder()
    learned_base = learned.wrap(base_responder)
    return AdaptiveCreativityResponder(learned_base, sparse)
