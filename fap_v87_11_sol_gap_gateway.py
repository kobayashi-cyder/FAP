#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
from http.server import ThreadingHTTPServer
from pathlib import Path

import fap_v87_10_program_synth_gateway as base
from fap_sol_gap_controller import CoverageCritic, DeliberationEngine, MultiIntentPlanner, PersistentGoalState

VERSION = "87.11-sol-gap"
ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime" / "v87_11"
RUNTIME.mkdir(parents=True, exist_ok=True)
STATE_DIR = RUNTIME / "goal_state"

# Preserve much more raw conversation and retain explicit goals/constraints separately.
base.MAX_HISTORY = 160
base.RUNTIME = RUNTIME
base.SESSIONS = RUNTIME / "sessions"
base.ARTIFACTS = RUNTIME / "artifacts"
base.EVAL_LOG = RUNTIME / "fap_eval.jsonl"
for p in (base.RUNTIME, base.SESSIONS, base.ARTIFACTS):
    p.mkdir(parents=True, exist_ok=True)
base.MEMORY = base.SessionMemory()
base.VERSION = VERSION


class FAPV8711(base.FAPV8710):
    def __init__(self):
        super().__init__()
        # Rebind generators to the V87.11 runtime paths.
        self.builder = base.SpecificationCompilerBuilder(base.ARTIFACTS, base.RUNTIME / "workspace")
        self.codegen = base.ProgramSynthesizer(base.ARTIFACTS, base.RUNTIME / "code_workspace")
        self.goal_state = PersistentGoalState(STATE_DIR)
        self.multi = MultiIntentPlanner()
        self.deliberation = DeliberationEngine(self.distilled)
        self.coverage = CoverageCritic()

    def capabilities(self) -> list[str]:
        caps = super().capabilities()
        extras = [
            "long-context:160-turns", "persistent-goal-ledger", "constraint-memory",
            "multi-intent-orchestration", "candidate-deliberation", "coverage-critic",
            "single-pass-replanning", "knowledge-boundary",
        ]
        for x in extras:
            if x not in caps:
                caps.append(x)
        return caps

    def status(self) -> dict:
        out = super().status()
        out.update({
            "version": VERSION,
            "state": "ready",
            "reasoning_controller": {
                "stage": 1,
                "raw_history_turns": 160,
                "persistent_goal_state": True,
                "multi_intent": True,
                "candidate_deliberation": True,
                "coverage_critic": True,
                "replan_rounds": 1,
            },
        })
        return out

    @staticmethod
    def _summary_query(text: str) -> bool:
        return bool(re.search(r"(今の|現在の|これまでの|保持している|覚えている).*(目的|目標|条件|制約|前提)|目的と条件|目標と条件", text))

    def _route_multi(self, tools, text: str, history: list[dict]) -> dict:
        replies = []
        calls = []
        all_ok = True
        artifacts = []
        for item in tools:
            intent = base.Intent(item.name, item.confidence, [(item.name, item.confidence)])
            res = self.route(intent, text, history)
            calls.append({"ability": item.name, "ok": bool(res.get("ok"))})
            all_ok = all_ok and bool(res.get("ok"))
            label = {
                "datetime": "日時", "calculator": "計算", "weather": "天気", "memory": "記憶"
            }.get(item.name, item.name)
            replies.append(f"{label}: {res.get('reply', '')}")
            artifacts.extend(res.get("artifacts", []))
        return {
            "ok": all_ok,
            "reply": "\n".join(replies),
            "confidence": min((x.confidence for x in tools), default=0.8),
            "artifacts": artifacts,
            "tool_calls": calls,
            "multi_intent": True,
        }

    def chat(self, text: str, sid: str) -> dict:
        history = base.MEMORY.load(sid)
        is_summary_query = self._summary_query(text)
        # Reading the current goal/constraints must not itself become a new goal.
        state = self.goal_state.load(sid) if is_summary_query else self.goal_state.update(sid, text)
        intent = self.intent.classify(text)
        deliberation = self.deliberation.plan(text, history, state)
        tools = self.multi.detect(text)

        if is_summary_query:
            result = {
                "ok": True,
                "reply": self.goal_state.summary(sid),
                "confidence": 0.96,
                "long_context": True,
            }
            ability = "memory"
            route = ["state", "long-context", "verify", "integrate"]
        elif tools:
            result = self._route_multi(tools, text, history)
            ability = "multi"
            route = ["decompose"] + [x.name for x in tools] + ["verify", "integrate"]
        else:
            # Vague follow-ups inherit the retained goal/constraints instead of being
            # interpreted as an isolated turn. This is the main long-horizon bridge.
            if intent.name == "chat" and state.get("open_goal") and re.search(r"(続き|次|どうする|進め|やって|それ|このまま)", text):
                enriched = f"目標: {state['open_goal']}\n制約: {' / '.join(state.get('constraints', [])[-8:])}\n現在の依頼: {text}"
                result = self.distilled.run(enriched, history)
            else:
                result = self.route(intent, text, history)
            ability = intent.name
            route = ["intent", intent.name, "deliberate", "verify", "integrate"]

        # One deterministic replan round: failed/unknown procedural chat with a retained
        # goal gets an explicit goal-aware retry rather than immediately giving up.
        replan_count = 0
        if (not result.get("ok") or result.get("needs_teacher")) and state.get("open_goal") and intent.name == "chat":
            replan_count = 1
            retry_text = f"目標: {state['open_goal']}\n現在の依頼: {text}\n制約: {' / '.join(state.get('constraints', [])[-8:])}"
            retry = self.distilled.run(retry_text, history)
            if retry.get("ok") and not retry.get("needs_teacher"):
                result = retry
                route.insert(-2, "replan")

        # Use the base verifier for compatibility, then add a coverage critic.
        verify_intent = intent if ability != "multi" else base.Intent("chat", 0.95, [("multi", 0.95)])
        verdict, critic_text = self.verify.verify(verify_intent, result)
        coverage = self.coverage.evaluate(text, result, state)
        if verdict == "OK" and coverage["verdict"] == "PARTIAL":
            verdict = "PARTIAL"
            critic_text += " 追加査定: " + ", ".join(coverage["issues"])

        reply = str(result.get("reply", "")).strip()
        confidence = float(result.get("confidence", 0.8))
        if ability not in {"chat", "multi", "memory"}:
            confidence = min(confidence, intent.confidence)

        base.MEMORY.append(sid, "user", text, {"intent": ability})
        base.MEMORY.append(sid, "assistant", reply, {"intent": ability, "verdict": verdict})

        event = {
            "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "session": base.safe_session(sid),
            "text": base.compact(text, 500),
            "intent": ability,
            "ok": bool(result.get("ok")),
            "verdict": verdict,
            "confidence": confidence,
            "selected_plan": deliberation.get("selected"),
            "replan_count": replan_count,
        }
        with self.lock:
            with base.EVAL_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return {
            "reply": reply,
            "ability": ability,
            "confidence": round(confidence, 3),
            "route": route,
            "critic": f"査定: {verdict}\n{critic_text}",
            "verdict": verdict,
            "artifacts": result.get("artifacts", []),
            "intent_candidates": intent.candidates,
            "tool_calls": result.get("tool_calls", []),
            "deliberation": deliberation,
            "coverage": coverage,
            "replan_count": replan_count,
            "goal_state": {
                "open_goal": state.get("open_goal", ""),
                "constraints": state.get("constraints", [])[-8:],
            },
            "status": self.status(),
        }


CORE = FAPV8711()
base.CORE = CORE
base.VERSION = VERSION


class Handler(base.Handler):
    server_version = "FAPV87.11SG"

    def do_GET(self):
        path = base.urllib.parse.urlparse(self.path).path
        if path.startswith("/api/v1/state"):
            query = base.urllib.parse.parse_qs(base.urllib.parse.urlparse(self.path).query)
            sid = base.safe_session((query.get("session") or ["default"])[0])
            self.send_json({"session": sid, "state": CORE.goal_state.load(sid), "summary": CORE.goal_state.summary(sid)})
            return
        super().do_GET()


def main() -> None:
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print(f"FAP V{VERSION} Sol-gap Reasoning Controller")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Local brain: V78 distilled circuits + persistent goal/constraint state")
    print("Reasoning: multi-intent orchestration + candidate deliberation + coverage critic + one replan")
    print("Code Generator: V87.10 Program IR preserved")
    print(f"Optional teacher: {base.OLLAMA_MODEL} @ {base.OLLAMA_BASE} (fallback={base.TEACHER_FALLBACK})")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
