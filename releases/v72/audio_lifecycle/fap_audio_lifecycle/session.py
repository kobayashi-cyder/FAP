from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class InvalidTransition(RuntimeError):
    pass


_ACTIVE_STATES = {"listening", "transcribing", "thinking", "speaking"}


@dataclass(frozen=True)
class AudioSessionSnapshot:
    state: str
    generation: int
    permission_granted: bool
    audio_focus_granted: bool
    captured_bytes: int
    captured_duration_ms: int
    transcript_chars: int
    response_chars: int
    last_reason: Optional[str]

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "generation": self.generation,
            "permission_granted": self.permission_granted,
            "audio_focus_granted": self.audio_focus_granted,
            "captured_bytes": self.captured_bytes,
            "captured_duration_ms": self.captured_duration_ms,
            "transcript_chars": self.transcript_chars,
            "response_chars": self.response_chars,
            "last_reason": self.last_reason,
        }


class AudioSession:
    """Half-duplex audio lifecycle state machine.

    This object intentionally stores counters and lifecycle state only. Raw microphone bytes,
    transcript text, and response text are not retained.
    """

    def __init__(self):
        self.state = "idle"
        self.generation = 0
        self.permission_granted = False
        self.audio_focus_granted = False
        self.captured_bytes = 0
        self.captured_duration_ms = 0
        self.transcript_chars = 0
        self.response_chars = 0
        self.last_reason: Optional[str] = None

    def snapshot(self) -> AudioSessionSnapshot:
        return AudioSessionSnapshot(
            state=self.state,
            generation=self.generation,
            permission_granted=self.permission_granted,
            audio_focus_granted=self.audio_focus_granted,
            captured_bytes=self.captured_bytes,
            captured_duration_ms=self.captured_duration_ms,
            transcript_chars=self.transcript_chars,
            response_chars=self.response_chars,
            last_reason=self.last_reason,
        )

    def _transition(self, expected: set[str], target: str) -> None:
        if self.state not in expected:
            raise InvalidTransition(f"{self.state} -> {target} is not allowed")
        self.state = target

    def begin_listening(self, *, permission_granted: bool, audio_focus_granted: bool) -> AudioSessionSnapshot:
        self._transition({"idle", "cancelled", "error"}, "listening")
        self.generation += 1
        self.permission_granted = bool(permission_granted)
        self.audio_focus_granted = bool(audio_focus_granted)
        self.captured_bytes = 0
        self.captured_duration_ms = 0
        self.transcript_chars = 0
        self.response_chars = 0
        self.last_reason = None
        if not self.permission_granted:
            self.state = "error"
            self.last_reason = "microphone_permission_denied"
        elif not self.audio_focus_granted:
            self.state = "error"
            self.last_reason = "audio_focus_denied"
        return self.snapshot()

    def capture_finished(self, *, byte_count: int, duration_ms: int) -> AudioSessionSnapshot:
        if byte_count < 0 or duration_ms < 0:
            raise ValueError("capture metrics must be non-negative")
        self._transition({"listening"}, "transcribing")
        self.captured_bytes = int(byte_count)
        self.captured_duration_ms = int(duration_ms)
        return self.snapshot()

    def transcript_ready(self, *, char_count: int) -> AudioSessionSnapshot:
        if char_count < 0:
            raise ValueError("transcript char count must be non-negative")
        self._transition({"transcribing"}, "thinking")
        self.transcript_chars = int(char_count)
        return self.snapshot()

    def response_ready(self, *, char_count: int) -> AudioSessionSnapshot:
        if char_count < 0:
            raise ValueError("response char count must be non-negative")
        self._transition({"thinking"}, "speaking")
        self.response_chars = int(char_count)
        return self.snapshot()

    def playback_finished(self) -> AudioSessionSnapshot:
        self._transition({"speaking"}, "idle")
        self.audio_focus_granted = False
        return self.snapshot()

    def cancel(self, reason: str = "cancelled") -> AudioSessionSnapshot:
        if self.state == "idle":
            self.last_reason = reason
            return self.snapshot()
        if self.state not in _ACTIVE_STATES and self.state not in {"error", "cancelled"}:
            raise InvalidTransition(f"cannot cancel from {self.state}")
        self.state = "cancelled"
        self.audio_focus_granted = False
        self.last_reason = str(reason)
        return self.snapshot()

    def on_audio_focus_lost(self) -> AudioSessionSnapshot:
        if self.state in _ACTIVE_STATES:
            return self.cancel("audio_focus_lost")
        self.audio_focus_granted = False
        return self.snapshot()

    def on_permission_revoked(self) -> AudioSessionSnapshot:
        self.permission_granted = False
        if self.state in {"listening", "transcribing"}:
            return self.cancel("microphone_permission_revoked")
        return self.snapshot()

    def fail(self, reason: str) -> AudioSessionSnapshot:
        if not reason:
            raise ValueError("error reason is required")
        self.state = "error"
        self.audio_focus_granted = False
        self.last_reason = str(reason)
        return self.snapshot()

    def reset(self) -> AudioSessionSnapshot:
        self.state = "idle"
        self.permission_granted = False
        self.audio_focus_granted = False
        self.captured_bytes = 0
        self.captured_duration_ms = 0
        self.transcript_chars = 0
        self.response_chars = 0
        self.last_reason = None
        return self.snapshot()
