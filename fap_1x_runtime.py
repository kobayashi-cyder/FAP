from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fap_interaction_fabric import (
    InteractionDispatch,
    InteractionEndpoint,
    InteractionFabric,
    InteractionRequest,
)
from fap_speech import SpeechRuntime, wrap_text_handler


TextHandler = Callable[[str], str]
Probe = Callable[[str], float]


class FAP1xRuntime:
    """Version-clean public 1.x composition boundary.

    The runtime owns the InteractionFabric and exposes a plain str -> str chat
    surface that can also be wrapped by the version-neutral speech layer.
    """

    VERSION = "1.0.01"

    def __init__(self, *, fabric: InteractionFabric | None = None) -> None:
        self.fabric = fabric or InteractionFabric()

    def register_text_endpoint(
        self,
        endpoint_id: str,
        handler: TextHandler,
        *,
        probe: Probe | None = None,
        channels: tuple[str, ...] = ("chat", "speech"),
        priority: float = 1.0,
        cost: float = 1.0,
        capabilities: tuple[str, ...] = (),
        task_families: tuple[str, ...] = (),
        task_forms: tuple[str, ...] = (),
        failure_specialties: tuple[str, ...] = (),
    ) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable")
        score = probe or (lambda _text: 1.0)

        def fabric_probe(request: InteractionRequest) -> float:
            return float(score(request.text))

        def fabric_handler(request: InteractionRequest, _budget: Any) -> Mapping[str, Any] | None:
            reply = handler(request.text)
            if reply is None:
                return None
            return {"text": str(reply), "ok": True}

        self.fabric.register(
            InteractionEndpoint(
                endpoint_id=endpoint_id,
                channels=channels,
                probe=fabric_probe,
                handler=fabric_handler,
                priority=priority,
                cost=cost,
                capabilities=capabilities,
                task_families=task_families,
                task_forms=task_forms,
                failure_specialties=failure_specialties,
            )
        )

    def dispatch(
        self,
        text: str,
        *,
        history: tuple[Mapping[str, Any], ...] = (),
        channel: str = "chat",
        pressure_hint: float = 0.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> InteractionDispatch:
        return self.fabric.dispatch(
            InteractionRequest(
                text=str(text),
                history=history,
                channel=channel,
                pressure_hint=pressure_hint,
                metadata=metadata,
            )
        )

    def chat(self, text: str) -> str:
        result = self.dispatch(text)
        if result.state != "handled" or not result.payload:
            return ""
        return str(result.payload.get("text", ""))

    def speech_once(
        self,
        *,
        runtime: SpeechRuntime | None = None,
        seconds: float = 4.0,
    ):
        return wrap_text_handler(self.chat, runtime)(seconds=seconds)
