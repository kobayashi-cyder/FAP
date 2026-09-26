from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
import re
from typing import Any

from fap_interaction_fabric import (
    InteractionDispatch,
    InteractionEndpoint,
    InteractionFabric,
    InteractionRequest,
)
from fap_semantic_memory import SemanticMemoryStore
from fap_1x_problem_decomposer import ProblemDecomposer
from fap_speech import SpeechRuntime, wrap_text_handler


TextHandler = Callable[[str], str]
Probe = Callable[[str], float]
EndpointHandler = Callable[[InteractionRequest, Any], Mapping[str, Any] | None]
ToolHandler = Callable[[str, Mapping[str, Any]], Mapping[str, Any] | str | None]
ToolVerifier = Callable[[Mapping[str, Any]], bool]


class FAP1xRuntime:
    """Version-clean public 1.x composition boundary.

    One runtime owns routing, bounded session history, optional semantic memory,
    verified tool endpoints, repository-coding adapters and the speech wrapper.
    It intentionally contains no benchmark-answer table and no direct main-branch
    mutation path.
    """

    VERSION = "1.0.01"

    def __init__(
        self,
        *,
        fabric: InteractionFabric | None = None,
        memory_root: str | Path | None = None,
        max_history_messages: int = 48,
    ) -> None:
        if not 2 <= int(max_history_messages) <= 256:
            raise ValueError("max_history_messages must be in [2, 256]")
        self.fabric = fabric or InteractionFabric()
        self.max_history_messages = int(max_history_messages)
        self.memory = (
            SemanticMemoryStore(Path(memory_root))
            if memory_root is not None
            else None
        )
        self._histories: dict[str, list[dict[str, Any]]] = {}
        self.task_decomposer = ProblemDecomposer()

    @staticmethod
    def _session_id(value: str) -> str:
        sid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(value or "default"))[:80]
        return sid or "default"

    def register_endpoint(
        self,
        endpoint_id: str,
        handler: EndpointHandler,
        *,
        probe: Callable[[InteractionRequest], float] | None = None,
        channels: tuple[str, ...] = ("chat",),
        priority: float = 1.0,
        cost: float = 1.0,
        capabilities: tuple[str, ...] = (),
        task_families: tuple[str, ...] = (),
        task_forms: tuple[str, ...] = (),
        failure_specialties: tuple[str, ...] = (),
    ) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable")
        fabric_probe = probe or (lambda _request: 1.0)
        self.fabric.register(
            InteractionEndpoint(
                endpoint_id=endpoint_id,
                channels=channels,
                probe=fabric_probe,
                handler=handler,
                priority=priority,
                cost=cost,
                capabilities=capabilities,
                task_families=task_families,
                task_forms=task_forms,
                failure_specialties=failure_specialties,
            )
        )

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

        def fabric_handler(
            request: InteractionRequest,
            _budget: Any,
        ) -> Mapping[str, Any] | None:
            reply = handler(request.text)
            if reply is None:
                return None
            return {"text": str(reply), "ok": True}

        self.register_endpoint(
            endpoint_id,
            fabric_handler,
            probe=fabric_probe,
            channels=channels,
            priority=priority,
            cost=cost,
            capabilities=capabilities,
            task_families=task_families,
            task_forms=task_forms,
            failure_specialties=failure_specialties,
        )

    def register_tool_endpoint(
        self,
        endpoint_id: str,
        tool: ToolHandler,
        *,
        verifier: ToolVerifier | None = None,
        probe: Probe | None = None,
        channels: tuple[str, ...] = ("tool",),
        priority: float = 1.0,
        cost: float = 1.0,
        capabilities: tuple[str, ...] = ("tool",),
        task_families: tuple[str, ...] = (),
        task_forms: tuple[str, ...] = (),
        failure_specialties: tuple[str, ...] = ("verification",),
    ) -> None:
        """Register a bounded tool whose output can be verified before routing stops.

        If verification fails, the endpoint emits ok=False. InteractionFabric
        rejects that route and continues to the next eligible endpoint.
        """
        if not callable(tool):
            raise TypeError("tool must be callable")
        score = probe or (lambda _text: 1.0)

        def fabric_probe(request: InteractionRequest) -> float:
            return float(score(request.text))

        def fabric_handler(
            request: InteractionRequest,
            _budget: Any,
        ) -> Mapping[str, Any] | None:
            metadata = (
                dict(request.metadata)
                if isinstance(request.metadata, Mapping)
                else {}
            )
            raw = tool(request.text, metadata)
            if raw is None:
                return None
            if isinstance(raw, Mapping):
                payload = dict(raw)
            else:
                payload = {"text": str(raw)}
            if verifier is not None:
                try:
                    verified = bool(verifier(payload))
                except Exception:
                    verified = False
                if not verified:
                    return {"ok": False, "verification": "failed"}
                payload["verification"] = "passed"
            payload.setdefault("ok", True)
            if "text" not in payload and "reply" in payload:
                payload["text"] = str(payload["reply"])
            return payload

        self.register_endpoint(
            endpoint_id,
            fabric_handler,
            probe=fabric_probe,
            channels=channels,
            priority=priority,
            cost=cost,
            capabilities=capabilities,
            task_families=task_families,
            task_forms=task_forms,
            failure_specialties=failure_specialties,
        )

    def register_repository_coding_endpoint(
        self,
        endpoint_id: str,
        coordinator: Any,
        proposer: Any,
        commands: Iterable[Any],
        *,
        repairer: Any | None = None,
        preferred_paths: tuple[str, ...] = (),
        probe: Probe | None = None,
        priority: float = 1.0,
        cost: float = 1.0,
    ) -> None:
        """Adapt RepositoryCodingCoordinator to the common 1.x routing contract."""
        if not hasattr(coordinator, "run"):
            raise TypeError("coordinator must expose run()")
        command_tuple = tuple(commands)

        def coding_tool(text: str, _metadata: Mapping[str, Any]) -> Mapping[str, Any]:
            result = coordinator.run(
                text,
                proposer,
                command_tuple,
                repairer=repairer,
                preferred_paths=preferred_paths,
            )
            state = str(getattr(result, "state", "unknown"))
            data = result.to_dict() if hasattr(result, "to_dict") else {"state": state}
            return {
                "ok": state == "verified_candidate",
                "text": state if state == "verified_candidate" else "",
                "state": state,
                "coding_result": data,
            }

        self.register_tool_endpoint(
            endpoint_id,
            coding_tool,
            probe=probe,
            channels=("coding",),
            priority=priority,
            cost=cost,
            capabilities=("coding", "repository", "verification"),
            task_families=("coding",),
            task_forms=("repository_change",),
            failure_specialties=("verification", "repair"),
        )

    def _auto_channel(self, text: str) -> tuple[str, dict[str, Any]]:
        decomposition = self.task_decomposer.decompose(text)
        descriptors = self.fabric.endpoint_descriptors

        if decomposition.task_kind == "coding":
            if any(
                "coding" in row["channels"] or "*" in row["channels"]
                for row in descriptors
            ):
                return "coding", decomposition.to_dict()

        if decomposition.task_kind == "calculation":
            for row in descriptors:
                channels = set(row["channels"])
                if "tool" not in channels and "*" not in channels:
                    continue
                capabilities = {str(x).lower() for x in row["capabilities"]}
                forms = {str(x).lower() for x in row["task_forms"]}
                families = {str(x).lower() for x in row["task_families"]}
                if (
                    capabilities & {"calculator", "calculation", "computation", "math", "numeric"}
                    or forms & {"calculation", "numeric", "arithmetic"}
                    or families & {"math", "calculation"}
                ):
                    return "tool", decomposition.to_dict()

        return "chat", decomposition.to_dict()

    def auto_turn(
        self,
        text: str,
        *,
        session_id: str = "default",
        pressure_hint: float = 0.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> InteractionDispatch:
        channel, decomposition = self._auto_channel(text)
        enriched = dict(metadata) if isinstance(metadata, Mapping) else {}
        enriched["auto_channel"] = channel
        enriched["task_decomposition"] = decomposition
        return self.run_turn(
            text,
            session_id=session_id,
            channel=channel,
            pressure_hint=pressure_hint,
            metadata=enriched,
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

    def run_turn(
        self,
        text: str,
        *,
        session_id: str = "default",
        channel: str = "chat",
        pressure_hint: float = 0.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> InteractionDispatch:
        sid = self._session_id(session_id)
        history = tuple(self._histories.get(sid, ()))
        enriched = dict(metadata) if isinstance(metadata, Mapping) else {}
        enriched.setdefault("session_id", sid)

        if self.memory is not None:
            self.memory.absorb_user(sid, text)
            recalled = self.memory.retrieve(sid, text, limit=8)
            if recalled:
                enriched["memory_context"] = tuple(
                    str(item.get("text", ""))[:360]
                    for item in recalled
                    if item.get("text")
                )

        result = self.dispatch(
            text,
            history=history,
            channel=channel,
            pressure_hint=pressure_hint,
            metadata=enriched,
        )
        reply = self._payload_text(result.payload)
        self._append_history(
            sid,
            {"role": "user", "content": str(text), "text": str(text), "channel": channel},
        )
        if reply:
            self._append_history(
                sid,
                {
                    "role": "assistant",
                    "content": reply,
                    "text": reply,
                    "channel": channel,
                    "endpoint_id": result.endpoint_id,
                },
            )

        if (
            self.memory is not None
            and result.state == "handled"
            and result.payload
            and bool(result.payload.get("ok", True))
            and channel in {"tool", "coding"}
        ):
            artifacts = result.payload.get("artifacts")
            safe_artifacts = list(artifacts) if isinstance(artifacts, list) else None
            self.memory.absorb_outcome(
                sid,
                text,
                "multi",
                "OK",
                safe_artifacts,
            )
        return result

    @staticmethod
    def _payload_text(payload: Mapping[str, Any] | None) -> str:
        if not payload:
            return ""
        for key in ("text", "reply", "message"):
            value = payload.get(key)
            if value is not None:
                return str(value)
        return ""

    def _append_history(self, sid: str, row: Mapping[str, Any]) -> None:
        rows = self._histories.setdefault(sid, [])
        rows.append(dict(row))
        if len(rows) > self.max_history_messages:
            del rows[: len(rows) - self.max_history_messages]

    def chat(
        self,
        text: str,
        *,
        session_id: str = "default",
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        result = self.run_turn(
            text,
            session_id=session_id,
            channel="chat",
            metadata=metadata,
        )
        if result.state != "handled":
            return ""
        return self._payload_text(result.payload)

    def tool_turn(
        self,
        text: str,
        *,
        session_id: str = "default",
        metadata: Mapping[str, Any] | None = None,
    ) -> InteractionDispatch:
        return self.run_turn(
            text,
            session_id=session_id,
            channel="tool",
            metadata=metadata,
        )

    def coding_turn(
        self,
        text: str,
        *,
        session_id: str = "default",
        metadata: Mapping[str, Any] | None = None,
    ) -> InteractionDispatch:
        return self.run_turn(
            text,
            session_id=session_id,
            channel="coding",
            metadata=metadata,
        )

    def session_snapshot(
        self,
        session_id: str = "default",
    ) -> tuple[dict[str, Any], ...]:
        sid = self._session_id(session_id)
        return tuple(dict(row) for row in self._histories.get(sid, ()))

    def clear_session(self, session_id: str = "default") -> None:
        self._histories.pop(self._session_id(session_id), None)

    def speech_once(
        self,
        *,
        runtime: SpeechRuntime | None = None,
        seconds: float = 4.0,
        session_id: str = "default",
    ):
        handler = lambda text: self.chat(text, session_id=session_id)
        return wrap_text_handler(handler, runtime)(seconds=seconds)
