#!/usr/bin/env python3
from __future__ import annotations

from contextvars import ContextVar
import datetime as dt
import json
import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_75_semantic_fabric_gateway as v75
from fap_session_continuity import (
    AdaptiveContextSelector,
    SessionRouteLedger,
)

base = v75.base
VERSION = "87.76-unified-chat"


class FAPV8776Unified(v75.FAPV8775Unified):
    """V87.75 plus adaptive multi-turn context and endpoint continuity."""

    def __init__(self):
        super().__init__()
        self.session_context = AdaptiveContextSelector(
            policy=self.interaction_policy,
            max_turns=128,
            max_turn_chars=20_000,
            hard_context_chars=250_000,
        )
        self.session_routes = SessionRouteLedger(
            max_sessions=128,
            max_events_per_session=32,
        )
        self._active_session: ContextVar[str] = ContextVar(
            "fap_v87_76_active_session",
            default="default",
        )
        self._active_context_stats: ContextVar[dict | None] = ContextVar(
            "fap_v87_76_active_context_stats",
            default=None,
        )
        self.chapter_dir = base.RUNTIME / "chapter_boundaries"
        self.chapter_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _is_new_chapter(text: str) -> bool:
        from fap_session_continuity import _NEW_CHAPTER
        return bool(_NEW_CHAPTER.search(str(text or "")))

    def _chapter_path(self, sid: str):
        return self.chapter_dir / f"{base.safe_session(sid)}.json"

    def _start_new_chapter(self, sid: str) -> dict:
        safe_sid = base.safe_session(sid)
        path = self._chapter_path(safe_sid)
        epoch = 0
        if path.exists():
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
                epoch = max(0, int(old.get("context_epoch", 0)))
            except Exception:
                epoch = 0
        marker = {
            "context_epoch": epoch + 1,
            "chapter_started_at": dt.datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        }
        # Destructive by design: a new chapter drops pre-boundary raw history.
        if hasattr(base.MEMORY, "clear"):
            base.MEMORY.clear(safe_sid)
        else:
            memory_path = base.MEMORY.path(safe_sid)
            try:
                memory_path.unlink()
            except FileNotFoundError:
                pass
        self.session_routes.clear(safe_sid)
        if hasattr(self, "goal_state") and hasattr(self.goal_state, "clear"):
            self.goal_state.clear(safe_sid)
        path.write_text(
            json.dumps(marker, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return marker

    def _chapter_marker(self, sid: str) -> dict | None:
        path = self._chapter_path(sid)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return {
                "context_epoch": max(1, int(raw.get("context_epoch", 1))),
                "chapter_started_at": str(raw.get("chapter_started_at") or ""),
            }
        except Exception:
            return None

    def chat(self, text: str, sid: str) -> dict:
        safe_sid = base.safe_session(sid)
        chapter_marker = (
            self._start_new_chapter(safe_sid)
            if self._is_new_chapter(text)
            else self._chapter_marker(safe_sid)
        )
        session_token = self._active_session.set(safe_sid)
        context_token = self._active_context_stats.set(None)
        try:
            result = dict(super().chat(text, safe_sid))
            context_stats = self._active_context_stats.get()
            if context_stats is not None:
                result["adaptive_session_context"] = context_stats
            result["session_route_continuity"] = (
                self.session_routes.snapshot(safe_sid).to_dict()
            )
            if chapter_marker is not None:
                result["chapter_boundary"] = dict(chapter_marker)
            return result
        finally:
            self._active_context_stats.reset(context_token)
            self._active_session.reset(session_token)

    def interaction_request_metadata(
        self,
        intent,
        text: str,
        history: list[dict],
    ) -> dict:
        metadata = dict(
            super().interaction_request_metadata(
                intent,
                text,
                history,
            )
        )
        sid = self._active_session.get()
        snapshot = self.session_routes.snapshot(sid)
        metadata["session_continuity"] = {
            "session_id": snapshot.session_id,
            "recent_endpoints": [
                event.endpoint_id for event in snapshot.events[-8:]
            ],
            "event_count": len(snapshot.events),
        }
        return metadata

    def route(self, intent, text: str, history: list[dict]) -> dict:
        selection = self.session_context.select(
            text,
            history,
            pressure_hint=0.0,
        )
        result = dict(
            super().route(
                intent,
                text,
                list(selection.history),
            )
        )

        dispatch = result.get("interaction_dispatch")
        if isinstance(dispatch, dict):
            endpoint_id = str(dispatch.get("endpoint_id") or "").strip()
            if endpoint_id:
                self.session_routes.record(
                    self._active_session.get(),
                    endpoint_id,
                    state="handled",
                    route_tags=tuple(
                        str(tag)
                        for tag in result.get("route_tags", ())
                        if isinstance(tag, str)
                    ),
                )

        self._active_context_stats.set(selection.to_dict())
        result["adaptive_session_context"] = selection.to_dict()
        result["session_route_continuity"] = self.session_routes.snapshot(
            self._active_session.get()
        ).to_dict()
        return result

    def clear_route_continuity(self, sid: str) -> None:
        self.session_routes.clear(base.safe_session(sid))

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.76",
            "adaptive-session-context",
            "exponential-linear-history-selection",
            "session-route-continuity",
            "content-free-endpoint-ledger",
            "cross-endpoint-multi-turn-context",
            "existing-session-storage-compatible",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.76",
                "session_continuity": {
                    "enabled": True,
                    "existing_persistent_message_store_reused": True,
                    "new_message_store_added": False,
                    "route_ledger_persistence": False,
                    "route_ledger_stores_message_text": False,
                    "adaptive_context_max_turns": self.session_context.max_turns,
                    "adaptive_context_hard_chars": (
                        self.session_context.hard_context_chars
                    ),
                    "route_ledger_max_sessions": self.session_routes.max_sessions,
                    "route_ledger_max_events": (
                        self.session_routes.max_events_per_session
                    ),
                    "fca_required": False,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8776Unified()
v75.CORE = CORE
v75.v74.CORE = CORE
v75.v74.v73.CORE = CORE
v75.v74.v73.v64.CORE = CORE
v75.v74.v73.v64.v63.CORE = CORE
v75.v74.v73.v64.v63.v62.CORE = CORE
v75.v74.v73.v64.v63.v62.v61.CORE = CORE
v75.v74.v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v75.Handler):
    server_version = "FAPV87.76SessionContinuity"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.76",
                    "state": "ready",
                }
            )
            return
        if path == "/api/v1/session-routes":
            sid = base.safe_session(
                (query.get("session") or ["default"])[0]
            )
            self.send_json(CORE.session_routes.snapshot(sid).to_dict())
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.76 ADAPTIVE SESSION CONTINUITY")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Existing persistent message sessions are reused.")
    print("Active context scales with the exponential-linear interaction budget.")
    print("Endpoint continuity ledger stores route metadata only, never message text.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
