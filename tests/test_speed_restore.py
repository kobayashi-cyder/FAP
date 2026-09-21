from __future__ import annotations

import json
from pathlib import Path
import tempfile

import fap_v87_10_program_synth_gateway as base
from fap_semantic_memory import AdaptiveRoutingLedger, SemanticMemoryStore
from fap_sol_gap_controller import PersistentGoalState
from fap_v87_12_semantic_adaptive_gateway import FAPV8712


class _FakePath:
    def __init__(self):
        self.content = ""
        self.writes = 0

    def exists(self):
        return bool(self.content)

    def read_text(self, encoding="utf-8"):
        return self.content

    def write_text(self, value, encoding="utf-8"):
        self.content = value
        self.writes += 1
        return len(value)


class _CountingSessionMemory(base.SessionMemory):
    def __init__(self):
        super().__init__()
        self.fake = _FakePath()

    def path(self, sid: str):
        return self.fake


def test_exchange_commits_whole_turn_with_one_write():
    mem = _CountingSessionMemory()
    mem.append_exchange(
        "s",
        "hello",
        "hi",
        {"intent": "chat"},
        {"intent": "chat", "verdict": "OK"},
    )
    assert mem.fake.writes == 1
    rows = json.loads(mem.fake.content)
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert [r["text"] for r in rows] == ["hello", "hi"]


def test_session_cache_avoids_re_reading_after_first_load():
    mem = _CountingSessionMemory()
    mem.append_exchange("s", "a", "b")
    # If load hits the in-memory cache, corrupting the backing representation
    # cannot affect the current process's hot history.
    mem.fake.content = "not json"
    rows = mem.load("s")
    assert [r["text"] for r in rows] == ["a", "b"]


def test_noise_does_not_create_semantic_memory_file():
    with tempfile.TemporaryDirectory() as td:
        mem = SemanticMemoryStore(Path(td))
        for i in range(40):
            mem.absorb_user("s", f"雑談メモ{i}")
        assert not mem.path("s").exists()
        assert mem.stats("s")["entries"] == 0


def test_noise_does_not_create_goal_state_file():
    with tempfile.TemporaryDirectory() as td:
        state = PersistentGoalState(Path(td))
        for i in range(40):
            out = state.update("s", f"今日は普通の雑談です {i}")
            assert out["open_goal"] == ""
        assert not state.path("s").exists()


def test_adaptive_ledger_reads_from_hot_cache():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "routing.json"
        ledger = AdaptiveRoutingLedger(path)
        ledger.record("Pythonコードを作って", "builder", "OK")
        first = ledger.load()
        path.write_text("{broken", encoding="utf-8")
        second = ledger.load()
        assert second is first
        assert "code" in second["families"]


def test_short_direct_chat_skips_diagnostic_deliberation():
    class Bomb:
        def plan(self, *args, **kwargs):
            raise AssertionError("deliberation should not run on direct fast path")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        core = FAPV8712()
        core.goal_state = PersistentGoalState(root / "goal")
        core.semantic = SemanticMemoryStore(root / "semantic")
        core.adaptive = AdaptiveRoutingLedger(root / "routing.json")
        core.deliberation = Bomb()

        old_memory = base.MEMORY
        old_sessions = base.SESSIONS
        try:
            base.SESSIONS = root / "sessions"
            base.SESSIONS.mkdir(parents=True, exist_ok=True)
            base.MEMORY = base.SessionMemory()
            out = core.chat("こんにちは", "speed-direct")
        finally:
            base.MEMORY = old_memory
            base.SESSIONS = old_sessions

        assert out["deliberation"]["selected"] == "direct"
        assert out["deliberation"]["skipped"] == "latency-fast-path"


def test_short_direct_chat_skips_semantic_retrieval():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        core = FAPV8712()
        core.goal_state = PersistentGoalState(root / "goal")
        core.semantic = SemanticMemoryStore(root / "semantic")
        core.adaptive = AdaptiveRoutingLedger(root / "routing.json")

        def forbidden(*args, **kwargs):
            raise AssertionError("semantic retrieve should not run on direct fast path")

        core.semantic.retrieve = forbidden

        old_memory = base.MEMORY
        old_sessions = base.SESSIONS
        try:
            base.SESSIONS = root / "sessions"
            base.SESSIONS.mkdir(parents=True, exist_ok=True)
            base.MEMORY = base.SessionMemory()
            out = core.chat("短い雑談です", "speed-no-retrieve")
        finally:
            base.MEMORY = old_memory
            base.SESSIONS = old_sessions

        assert out["ability"] == "chat"
