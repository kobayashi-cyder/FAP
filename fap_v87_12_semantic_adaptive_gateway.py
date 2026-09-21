#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
from http.server import ThreadingHTTPServer
from pathlib import Path

import fap_v87_10_program_synth_gateway as base
import fap_v87_11_sol_gap_gateway as v11
from fap_semantic_memory import AdaptiveRoutingLedger, SemanticMemoryStore
from fap_sol_gap_controller import CoverageCritic, DeliberationEngine, MultiIntentPlanner, PersistentGoalState

VERSION = "87.12-semantic-adaptive"
ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime" / "v87_12"
RUNTIME.mkdir(parents=True, exist_ok=True)
STATE_DIR = RUNTIME / "goal_state"
SEMANTIC_DIR = RUNTIME / "semantic_memory"
ROUTING_FILE = RUNTIME / "adaptive_routing.json"

# Raw chat is now deliberately smaller. Important state survives in compact
# semantic memory rather than by keeping every turn forever.
base.MAX_HISTORY = 48
base.RUNTIME = RUNTIME
base.SESSIONS = RUNTIME / "sessions"
base.ARTIFACTS = RUNTIME / "artifacts"
base.EVAL_LOG = RUNTIME / "fap_eval.jsonl"
for p in (base.RUNTIME, base.SESSIONS, base.ARTIFACTS):
    p.mkdir(parents=True, exist_ok=True)
base.MEMORY = base.SessionMemory()
base.VERSION = VERSION


class FAPV8712(v11.FAPV8711):
    def __init__(self):
        # Avoid depending on V87.11 module globals for runtime paths.
        base.FAPV8710.__init__(self)
        self.builder = base.SpecificationCompilerBuilder(base.ARTIFACTS, base.RUNTIME / "workspace")
        self.codegen = base.ProgramSynthesizer(base.ARTIFACTS, base.RUNTIME / "code_workspace")
        self.goal_state = PersistentGoalState(STATE_DIR)
        self.multi = MultiIntentPlanner()
        self.deliberation = DeliberationEngine(self.distilled)
        self.coverage = CoverageCritic()
        self.semantic = SemanticMemoryStore(SEMANTIC_DIR)
        self.adaptive = AdaptiveRoutingLedger(ROUTING_FILE)

    def capabilities(self) -> list[str]:
        caps = super().capabilities()
        # Replace the old raw-history label with the new architecture description.
        caps = [x for x in caps if x != "long-context:160-turns"]
        extras = [
            "raw-context:48-turns",
            "semantic-long-term-memory",
            "semantic-compaction",
            "preference-supersession",
            "experience-memory",
            "adaptive-routing-ledger",
            "outcome-weighted-routing",
            "routing-safety-locks",
        ]
        for x in extras:
            if x not in caps:
                caps.append(x)
        return caps

    def status(self) -> dict:
        out = base.FAPV8710.status(self)
        out.update({
            "version": VERSION,
            "state": "ready",
            "reasoning_controller": {
                "stage": 2,
                "raw_history_turns": base.MAX_HISTORY,
                "persistent_goal_state": True,
                "semantic_memory": True,
                "semantic_memory_slots": self.semantic.MAX_ENTRIES,
                "semantic_compaction": True,
                "preference_supersession": True,
                "multi_intent": True,
                "candidate_deliberation": True,
                "coverage_critic": True,
                "replan_rounds": 1,
                "adaptive_routing": True,
                "adaptive_routing_safety_locks": True,
            },
        })
        out["capabilities"] = self.capabilities()
        return out

    @staticmethod
    def _semantic_recall_query(text: str) -> bool:
        t = str(text or "")
        return bool(
            re.search(r"(長期記憶|重要情報|覚えている|保持している|これまでの設定)", t)
            or re.search(r"(標準|デフォルト|出力|回答|言語|形式|合言葉|好み|優先).*(何|どれ|確認|教えて|\?|？|は$)", t)
            or re.search(r"(何|どれ).*(標準|デフォルト|出力|回答|言語|形式|合言葉|好み|優先)", t)
        )

    def _semantic_reply(self, sid: str, text: str) -> dict | None:
        rows = self.semantic.retrieve(sid, text, 8)
        if not rows:
            return None
        return {
            "ok": True,
            "reply": self.semantic.render(sid, text, 8),
            "confidence": 0.95,
            "semantic_memory": True,
        }

    @staticmethod
    def _needs_deliberation(text: str, intent, state: dict, tools) -> bool:
        """Keep plan scoring off the hot path unless it can add diagnostic value.

        Deliberation metadata does not choose the actual route in V87.12, so
        paying for distilled circuit activation on every greeting or short
        direct request only adds latency.
        """
        if tools:
            return True
        if len(str(text or "")) >= 240:
            return True
        if state.get("open_goal") and re.search(r"(続き|次|どうする|進め|それ|このまま)", str(text or "")):
            return True
        if re.search(r"(計画|比較|検討|設計|分析|理由|なぜ|どうすれば|改善|最適|戦略|手順)", str(text or "")):
            return True
        return getattr(intent, "name", "chat") in {"builder"} and len(str(text or "")) >= 140

    @staticmethod
    def _direct_deliberation(state: dict) -> dict:
        return {
            "candidates": [],
            "selected": "direct",
            "goal_present": bool(state.get("open_goal")),
            "constraint_count": len(state.get("constraints", [])),
            "skipped": "latency-fast-path",
        }

    def _route_adapted(self, intent, adaptation: dict, text: str, history: list[dict]) -> tuple[dict, str, object]:
        selected = adaptation.get("selected", intent.name)
        effective = intent
        route_text = text
        if selected != intent.name:
            effective = base.Intent(str(selected), min(0.92, max(0.70, float(intent.confidence))), intent.candidates)
            # The builder itself uses an explicit create verb as a safety gate. If
            # adaptive routing learned that an implicit code request belongs there,
            # add only the gate phrase; user content remains unchanged.
            if selected == "builder" and adaptation.get("reason") == "learned code-request prior":
                route_text = "作成して: " + text
        return self.route(effective, route_text, history), str(selected), effective

    def chat(self, text: str, sid: str) -> dict:
        history = base.MEMORY.load(sid)
        is_goal_summary = self._summary_query(text)
        semantic_query = self._semantic_recall_query(text)

        # Querying memory must not itself become a remembered preference/fact.
        if not semantic_query and not is_goal_summary:
            self.semantic.absorb_user(sid, text)
        state = self.goal_state.load(sid) if (semantic_query or is_goal_summary) else self.goal_state.update(sid, text)

        intent = self.intent.classify(text)
        tools = self.multi.detect(text)
        deliberation = (
            self.deliberation.plan(text, history, state)
            if self._needs_deliberation(text, intent, state, tools)
            else self._direct_deliberation(state)
        )
        adaptation = {
            "family": "deferred",
            "base": intent.name,
            "selected": intent.name,
            "applied": False,
            "reason": "not needed on this route",
            "evidence": {},
        }

        if is_goal_summary:
            semantic_rows = self.semantic.retrieve(sid, text, 6)
            semantic_tail = ""
            if semantic_rows:
                semantic_tail = "\n" + self.semantic.render(sid, text, 6)
            result = {
                "ok": True,
                "reply": self.goal_state.summary(sid) + semantic_tail,
                "confidence": 0.96,
                "long_context": True,
            }
            ability = "memory"
            effective_intent = base.Intent("memory", 0.96, [("memory", 0.96)])
            route = ["state", "semantic-memory", "long-context", "verify", "integrate"]
        elif semantic_query:
            sem = self._semantic_reply(sid, text)
            if sem is not None:
                result = sem
                ability = "memory"
                effective_intent = base.Intent("memory", 0.95, [("memory", 0.95)])
                route = ["semantic-retrieve", "verify", "integrate"]
            else:
                result = {"ok": True, "reply": "長期意味記憶に、この質問へ対応する明示情報はありません。", "confidence": 0.92}
                ability = "memory"
                effective_intent = base.Intent("memory", 0.92, [("memory", 0.92)])
                route = ["semantic-retrieve", "verify", "integrate"]
        elif tools:
            result = self._route_multi(tools, text, history)
            ability = "multi"
            effective_intent = base.Intent("chat", 0.95, [("multi", 0.95)])
            route = ["decompose"] + [x.name for x in tools] + ["verify", "integrate"]
        else:
            # Adaptive routing is needed only for the ordinary routing branch.
            # Summary/memory/multi requests no longer pay for ledger inspection.
            adaptation = self.adaptive.suggest(text, intent)

            # Semantic retrieval is only consumed by vague goal-followups. The old
            # path performed a full semantic scan on every normal chat turn.
            followup = bool(
                intent.name == "chat"
                and state.get("open_goal")
                and re.search(r"(続き|次|どうする|進め|やって|それ|このまま)", text)
            )
            if followup:
                semantic_rows = self.semantic.retrieve(sid, text, 4)
                semantic_context = " / ".join(
                    str(x.get("text", ""))
                    for x in semantic_rows
                    if x.get("category") in {"preference", "constraint", "goal"}
                )
                enriched = f"目標: {state['open_goal']}\n制約: {' / '.join(state.get('constraints', [])[-8:])}"
                if semantic_context:
                    enriched += f"\n長期意味記憶: {semantic_context}"
                enriched += f"\n現在の依頼: {text}"
                result = self.distilled.run(enriched, history)
                ability = intent.name
                effective_intent = intent
            else:
                result, ability, effective_intent = self._route_adapted(intent, adaptation, text, history)
            route = ["intent", intent.name]
            if result.get("factual_qa"):
                route += ["factual-qa"]
            if adaptation.get("applied"):
                route += ["adaptive-route", ability]
            route += ["deliberate", "semantic-context", "verify", "integrate"]

        replan_count = 0
        if (not result.get("ok") or result.get("needs_teacher")) and state.get("open_goal") and intent.name == "chat" and ability == "chat":
            replan_count = 1
            sem = self.semantic.retrieve(sid, text, 4)
            mem = " / ".join(str(x.get("text", "")) for x in sem)
            retry_text = f"目標: {state['open_goal']}\n現在の依頼: {text}\n制約: {' / '.join(state.get('constraints', [])[-8:])}"
            if mem:
                retry_text += f"\n長期意味記憶: {mem}"
            retry = self.distilled.run(retry_text, history)
            if retry.get("ok") and not retry.get("needs_teacher"):
                result = retry
                route.insert(-2, "replan")

        verify_intent = effective_intent if ability != "multi" else base.Intent("chat", 0.95, [("multi", 0.95)])
        verdict, critic_text = self.verify.verify(verify_intent, result)
        coverage = self.coverage.evaluate(text, result, state)
        if verdict == "OK" and coverage["verdict"] == "PARTIAL":
            verdict = "PARTIAL"
            critic_text += " 追加査定: " + ", ".join(coverage["issues"])

        reply = str(result.get("reply", "")).strip()
        confidence = float(result.get("confidence", 0.8))
        if ability not in {"chat", "multi", "memory"}:
            confidence = min(confidence, float(getattr(effective_intent, "confidence", intent.confidence)))

        if hasattr(base.MEMORY, "append_exchange"):
            base.MEMORY.append_exchange(
                sid,
                text,
                reply,
                {"intent": ability},
                {"intent": ability, "verdict": verdict},
            )
        else:
            base.MEMORY.append(sid, "user", text, {"intent": ability})
            base.MEMORY.append(sid, "assistant", reply, {"intent": ability, "verdict": verdict})

        # Learn only after verification. This is outcome learning, not self-modifying code.
        self.adaptive.record(text, ability, verdict)
        self.semantic.absorb_outcome(sid, text, ability, verdict, result.get("artifacts", []))
        semantic_stats = self.semantic.stats(sid)

        event = {
            "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "session": base.safe_session(sid),
            "text": base.compact(text, 500),
            "intent": ability,
            "base_intent": intent.name,
            "adaptive_applied": bool(adaptation.get("applied")),
            "ok": bool(result.get("ok")),
            "verdict": verdict,
            "confidence": confidence,
            "selected_plan": deliberation.get("selected"),
            "replan_count": replan_count,
            "semantic_entries": semantic_stats.get("entries", 0),
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
            "adaptive_routing": adaptation,
            "semantic_memory": semantic_stats,
            "goal_state": {
                "open_goal": state.get("open_goal", ""),
                "constraints": state.get("constraints", [])[-8:],
            },
            "status": self.chat_status(),
        }


CORE = FAPV8712()
base.CORE = CORE
base.VERSION = VERSION


class Handler(v11.Handler):
    server_version = "FAPV87.12SA"

    def do_GET(self):
        parsed = base.urllib.parse.urlparse(self.path)
        path = parsed.path
        query = base.urllib.parse.parse_qs(parsed.query)
        if path == "/api/v1/semantic-memory":
            sid = base.safe_session((query.get("session") or ["default"])[0])
            q = (query.get("q") or ["重要情報"])[0]
            self.send_json({
                "session": sid,
                "stats": CORE.semantic.stats(sid),
                "results": CORE.semantic.retrieve(sid, q, 12),
                "summary": CORE.semantic.render(sid, q, 12),
            })
            return
        if path == "/api/v1/routing-stats":
            self.send_json(CORE.adaptive.stats())
            return
        super().do_GET()


def main() -> None:
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print(f"FAP V{VERSION} Semantic Memory + Adaptive Routing")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Raw context: 48 turns; important state is compacted into semantic long-term memory")
    print("Memory: goals + constraints + preferences + explicit facts + verified experiences")
    print("Routing: verified outcomes update bounded routing priors; explicit intents stay locked")
    print("Code Generator: V87.10 Program IR preserved")
    print(f"Optional teacher: {base.OLLAMA_MODEL} @ {base.OLLAMA_BASE} (fallback={base.TEACHER_FALLBACK})")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
