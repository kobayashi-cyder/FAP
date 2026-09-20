from __future__ import annotations

from typing import Callable, Optional

from .core import LocalAdaptiveCore, LocalAdaptiveResponder


def build_v81_responder(
    base_responder: Callable[[str, str, str], str],
    *,
    core: Optional[LocalAdaptiveCore] = None,
):
    """Compose V81 ahead of V79 creativity and V78 teacher-learning guidance.

    Call order:
        user -> V81 local adaptation -> V79 creativity -> V78 learned guidance -> base
    """
    if not callable(base_responder):
        raise TypeError("base_responder must be callable")

    from fap_creativity import build_v79_responder

    lower_stack = build_v79_responder(base_responder)
    return LocalAdaptiveResponder(
        lower_stack,
        core=core or LocalAdaptiveCore(),
    )
