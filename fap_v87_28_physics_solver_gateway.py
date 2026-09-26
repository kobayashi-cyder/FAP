#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from http.server import ThreadingHTTPServer

import fap_v87_27_physics_knowledge_gateway as v27
from fap_physics_solver_v2 import ExpandedPhysicsSolver

base = v27.base
VERSION = "87.28-physics-solvers"


class FAPV8728(v27.FAPV8727):
    def __init__(self):
        super().__init__()
        self.physics_solver_v2 = ExpandedPhysicsSolver()

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "expanded-deterministic-physics-solvers",
            "mechanics-equation-solvers",
            "wave-equation-solvers",
            "electromagnetism-equation-solvers",
            "thermal-radiation-solvers",
            "radioactive-decay-solver",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out["version"] = VERSION
        out["physics_solver_v2"] = {
            "deterministic_only": True,
            "benchmark_answer_keys": 0,
            "fallback": "V87.27 unchanged",
        }
        out["capabilities"] = self.capabilities()
        return out

    def chat(self, text: str, sid: str):
        task = self.mcq_parser.parse(text)
        if task is None:
            return super().chat(text, sid)

        solved = self.physics_solver_v2.run(task)
        if solved is None:
            return super().chat(text, sid)

        verdict, critic_text = self.mcq_verifier.verify(task, solved)
        reply = str(solved.get("reply", "")).strip()
        confidence = float(solved.get("confidence", 0.25))
        history_intent = "structured_mcq"

        if hasattr(base.MEMORY, "append_exchange"):
            base.MEMORY.append_exchange(
                sid,
                text,
                reply,
                {"intent": history_intent},
                {
                    "intent": history_intent,
                    "verdict": verdict,
                    "decision_source": solved.get("decision_source"),
                },
            )
        else:
            base.MEMORY.append(sid, "user", text, {"intent": history_intent})
            base.MEMORY.append(
                sid,
                "assistant",
                reply,
                {
                    "intent": history_intent,
                    "verdict": verdict,
                    "decision_source": solved.get("decision_source"),
                },
            )

        shadow_intent = self.intent.classify(text)
        event = {
            "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "session": base.safe_session(sid),
            "text": base.compact(text, 500),
            "intent": history_intent,
            "shadow_base_intent": shadow_intent.name,
            "domain": task.domain,
            "decision_source": solved.get("decision_source"),
            "physics_solver_v2": True,
            "ok": True,
            "verdict": verdict,
            "confidence": confidence,
        }
        with self.lock:
            with base.EVAL_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return {
            "reply": reply,
            "ability": "structured_mcq",
            "confidence": round(confidence, 3),
            "route": [
                "structured-detect",
                "instruction-content-separate",
                "physics-deterministic-v2",
                "contract-verify",
                "integrate",
            ],
            "critic": f"査定: {verdict}\n{critic_text}",
            "verdict": verdict,
            "artifacts": [],
            "intent_candidates": [
                ("structured_mcq", 1.0),
                ("shadow:" + shadow_intent.name, shadow_intent.confidence),
            ],
            "tool_calls": [],
            "structured_mcq": {
                "domain": task.domain,
                "decision_source": solved.get("decision_source"),
                "forced_choice": False,
                "answer_contract": "Answer: $LETTER",
                "physics_deterministic": solved.get("physics_deterministic", {}),
            },
            "status": self.chat_status(),
        }


CORE = FAPV8728()
v27.CORE = CORE
v27.v26.CORE = CORE
v27.v26.v25.CORE = CORE
v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v27.Handler):
    server_version = "FAPV87.28PS"


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print(f"FAP V{VERSION} Expanded Physics Solvers")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Deterministic general physics equations run before V87.27.")
    print("Unresolved requests delegate to V87.27 unchanged.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
