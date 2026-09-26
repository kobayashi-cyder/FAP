from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_audio_lifecycle import AudioSession, InvalidTransition


class AudioSessionTests(unittest.TestCase):
    def test_happy_path_half_duplex(self):
        s = AudioSession()
        self.assertEqual(s.begin_listening(permission_granted=True, audio_focus_granted=True).state, "listening")
        self.assertEqual(s.capture_finished(byte_count=32000, duration_ms=1000).state, "transcribing")
        self.assertEqual(s.transcript_ready(char_count=8).state, "thinking")
        self.assertEqual(s.response_ready(char_count=20).state, "speaking")
        snap = s.playback_finished()
        self.assertEqual(snap.state, "idle")
        self.assertFalse(snap.audio_focus_granted)

    def test_permission_denied_fails_before_capture(self):
        s = AudioSession()
        snap = s.begin_listening(permission_granted=False, audio_focus_granted=True)
        self.assertEqual(snap.state, "error")
        self.assertEqual(snap.last_reason, "microphone_permission_denied")
        with self.assertRaises(InvalidTransition):
            s.capture_finished(byte_count=1, duration_ms=1)

    def test_audio_focus_denied_fails_before_capture(self):
        s = AudioSession()
        snap = s.begin_listening(permission_granted=True, audio_focus_granted=False)
        self.assertEqual(snap.state, "error")
        self.assertEqual(snap.last_reason, "audio_focus_denied")

    def test_cannot_listen_while_speaking(self):
        s = AudioSession()
        s.begin_listening(permission_granted=True, audio_focus_granted=True)
        s.capture_finished(byte_count=2, duration_ms=1)
        s.transcript_ready(char_count=1)
        s.response_ready(char_count=1)
        with self.assertRaises(InvalidTransition):
            s.begin_listening(permission_granted=True, audio_focus_granted=True)

    def test_focus_loss_cancels_active_session(self):
        s = AudioSession()
        s.begin_listening(permission_granted=True, audio_focus_granted=True)
        snap = s.on_audio_focus_lost()
        self.assertEqual(snap.state, "cancelled")
        self.assertEqual(snap.last_reason, "audio_focus_lost")
        self.assertFalse(snap.audio_focus_granted)

    def test_permission_revoke_cancels_listening_or_transcribing(self):
        for reach_transcribing in (False, True):
            s = AudioSession()
            s.begin_listening(permission_granted=True, audio_focus_granted=True)
            if reach_transcribing:
                s.capture_finished(byte_count=2, duration_ms=1)
            snap = s.on_permission_revoked()
            self.assertEqual(snap.state, "cancelled")
            self.assertEqual(snap.last_reason, "microphone_permission_revoked")
            self.assertFalse(snap.permission_granted)

    def test_snapshot_contains_no_raw_audio_or_text(self):
        s = AudioSession()
        s.begin_listening(permission_granted=True, audio_focus_granted=True)
        s.capture_finished(byte_count=1234, duration_ms=77)
        s.transcript_ready(char_count=9)
        snap = s.snapshot().to_dict()
        self.assertEqual(snap["captured_bytes"], 1234)
        self.assertEqual(snap["transcript_chars"], 9)
        for forbidden in ("data", "pcm", "audio", "transcript", "text", "response_text"):
            self.assertNotIn(forbidden, snap)

    def test_cancel_then_restart_increments_generation(self):
        s = AudioSession()
        first = s.begin_listening(permission_granted=True, audio_focus_granted=True)
        s.cancel("user_cancel")
        second = s.begin_listening(permission_granted=True, audio_focus_granted=True)
        self.assertEqual(second.generation, first.generation + 1)
        self.assertEqual(second.state, "listening")
        self.assertIsNone(second.last_reason)

    def test_reset_clears_transient_metrics(self):
        s = AudioSession()
        s.begin_listening(permission_granted=True, audio_focus_granted=True)
        s.capture_finished(byte_count=100, duration_ms=20)
        snap = s.reset()
        self.assertEqual(snap.state, "idle")
        self.assertEqual(snap.captured_bytes, 0)
        self.assertEqual(snap.captured_duration_ms, 0)

    def test_negative_metrics_rejected(self):
        s = AudioSession()
        s.begin_listening(permission_granted=True, audio_focus_granted=True)
        with self.assertRaises(ValueError):
            s.capture_finished(byte_count=-1, duration_ms=0)


if __name__ == "__main__":
    unittest.main()
