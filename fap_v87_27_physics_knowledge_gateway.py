#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from http.server import ThreadingHTTPServer

import fap_v87_26_scientific_reasoning_gateway as v26
from fap_physics_knowledge import PhysicsKnowledgeReasoner, PhysicsKnowledgeStore

base = v26.base
VERSION = "87.27-physics-knowledge"


class FAPV8727(v26.FAPV8726):
    def __init__(self):
        super().__init__()
        self.physics_reasoner = PhysicsKnowledgeReasoner(self.science_reasoner)

    def capabilities(self):
        caps = super().capabilities()
        for x in [
            "physics-knowledge-store",
            "physics-retrieval",
            "physics-formula-memory",
            "physics-condition-memory",
            "physics-misconception-memory",
        ]:
            if x not in caps:
                caps.append(x)
        return caps

    def status(self):
        out = super().status()
        out["version"] = VERSION
        out["physics_knowledge"] = PhysicsKnowledgeStore.stats()
        out["capabilities"] = self.capabilities()
        return out

    def chat(self, text: str, sid: str):
        task = self.mcq_parser.parse(text)
        if task is None:
            return super().chat(text, sid)

        history = base.MEMORY.load(sid)
        shadow_intent = self.intent.classify(text)
        result = self.physics_reasoner.run(
            task, history, teacher_allowed=bool(base.TEACHER_FALLBACK)
        )
        verdict, critic_text = self.mcq_verifier.verify(task, result)
        reply = str(result.get("reply", "")).strip()
        confidence = float(result.get("confidence", 0.25))

        base.MEMORY.append(sid, "user", text, {"intent": "structured_mcq"})
        base.MEMORY.append(sid, "assistant", reply, {
            "intent": "structured_mcq",
            "verdict": verdict,
            "decision_source": result.get("decision_source"),
        })

        event = {
            "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "session": base.safe_session(sid),
            "text": base.compact(text, 500),
            "intent": "structured_mcq",
            "shadow_base_intent": shadow_intent.name,
            "domain": task.domain,
            "decision_source": result.get("decision_source"),
            "physics_used": bool((result.get("physics_knowledge") or {}).get("used")),
            "ok": bool(result.get("ok")),
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
                "domain-infer",
                "physics-retrieve" if task.domain == "physics" else "option-conditioned-science",
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
                "decision_source": result.get("decision_source"),
                "forced_choice": bool(result.get("forced_choice")),
                "answer_contract": "Answer: $LETTER",
                "physics_knowledge": result.get("physics_knowledge", {}),
                "option_assessments": result.get("option_assessments", []),
            },
            "status": self.status(),
        }


CORE = FAPV8727()
v26.CORE = CORE
v26.v25.CORE = CORE
v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v26.Handler):
    server_version = "FAPV87.27PK"


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print(f"FAP V{VERSION} Physics Knowledge Store")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Physics-only retrieval: concepts + laws + formulas + conditions + misconceptions")
    print("Non-physics MCQ: inherited V87.26 path")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
