from __future__ import annotations

from typing import Callable, Optional

from .engine import CreativityAugmentedResponder, CreativityEngine


def build_v79_responder(
    base_responder: Callable[[str, str, str], str],
    *,
    engine: Optional[CreativityEngine] = None,
):
    """Compose V79 creativity in front of V78 teacher-learning guidance.

    Call order:
        user -> V79 creativity -> V78 learned guidance -> base responder
    """
    if not callable(base_responder):
        raise TypeError("base_responder must be callable")

    from fap_teacher_learning import TeacherLearningResponder

    learned = TeacherLearningResponder()
    learned_base = learned.wrap(base_responder)
    return CreativityAugmentedResponder(
        learned_base,
        engine=engine or CreativityEngine(),
    )
