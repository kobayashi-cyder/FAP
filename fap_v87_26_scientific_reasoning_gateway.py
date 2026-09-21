#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from http.server import ThreadingHTTPServer

import fap_v87_25_structured_reasoning_gateway as v25
from fap_scientific_reasoning import OptionConditionedScientificReasoner, science_rule_stats

base = v25.base
VERSION = "87.26-scientific-reasoning"


class FAPV8726(v25.FAPV8725):
    def __init__(self):
        super().__init__()
        self.science_reasoner = OptionConditionedScientificReasoner(self.mcq_reasoner)

    def capabilities(self):
        caps = super().capabilities()
        for x in [
            "option-conditioned-scientific-reasoning",
            "per-option-evidence",
            "per-option-contradiction",
            "negative-question-polarity",
            "scientific-rule-retrieval",
        ]:
            if x not in caps:
                caps.append(x)
        return caps

    def status(self):
        out = super().status()
        out["version"] = VERSION
        out["scientific_reasoning"] = {
            "stage": 1,
            "option_conditioned": True,
            "rule_stats": science_rule_stats(),
            "fallback": "V87.25 structured reasoner",
        }
        out["capabilities"] = self.capabilities()
        return out

    def chat(self, text: str, sid: str):
        task = self.mcq_parser.parse(text)
        if task is None:
            return super().chat(text, sid)

        history = base.MEMORY.load(sid)
        shadow_intent = self.intent.classify(text)
        result = self.science_reasoner.run(
            task,
            history,
            teacher_allowed=bool(base.TEACHER_FALLBACK),
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
            "forced_choice": bool(result.get("forced_choice")),
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
                "option-conditioned-science",
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
                "option_assessments": result.get("option_assessments", []),
            },
            "status": self.status(),
        }


CORE = FAPV8726()
v25.CORE = CORE
v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v25.Handler):
    server_version = "FAPV87.26SR"


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print(f"FAP V{VERSION} Option-Conditioned Scientific Reasoner")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("A-D options are evaluated independently for support and contradiction.")
    print("Low-margin evidence falls back to V87.25 unresolved behavior.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
