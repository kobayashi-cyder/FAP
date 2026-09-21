#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from http.server import ThreadingHTTPServer

import fap_v87_12_semantic_adaptive_gateway as v12
from fap_benchmark_reasoning import StructuredMCQParser, StructuredMCQReasoner, StructuredMCQVerifier

base = v12.base
VERSION = "87.25-structured-reasoning"


class FAPV8725(v12.FAPV8712):
    """V87.12 text runtime plus a narrow structured-question lane."""

    def __init__(self):
        super().__init__()
        self.mcq_parser = StructuredMCQParser()
        self.mcq_reasoner = StructuredMCQReasoner(self.distilled, self.e2b)
        self.mcq_verifier = StructuredMCQVerifier()

    def capabilities(self) -> list[str]:
        caps = super().capabilities()
        extras = [
            "structured-mcq-routing",
            "benchmark-instruction-separation",
            "mcq-domain-inference",
            "mcq-answer-contract",
            "mcq-keyword-router-shield",
            "mcq-independent-verdict-separation",
        ]
        for item in extras:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self) -> dict:
        out = super().status()
        out["version"] = VERSION
        out["structured_reasoning"] = {
            "stage": 1,
            "explicit_mcq_only": True,
            "required_choices": ["A", "B", "C", "D"],
            "instruction_content_separation": True,
            "keyword_router_shield": True,
            "answer_contract": "Answer: $LETTER",
            "teacher_optional": bool(base.TEACHER_FALLBACK),
            "unresolved_fallback": "content-stable low-confidence forced choice",
        }
        out["capabilities"] = self.capabilities()
        return out

    def chat(self, text: str, sid: str) -> dict:
        task = self.mcq_parser.parse(text)
        if task is None:
            return super().chat(text, sid)

        history = base.MEMORY.load(sid)
        shadow_intent = self.intent.classify(text)
        result = self.mcq_reasoner.run(
            task,
            history,
            teacher_allowed=bool(base.TEACHER_FALLBACK),
        )
        verdict, critic_text = self.mcq_verifier.verify(task, result)
        reply = str(result.get("reply", "")).strip()
        confidence = float(result.get("confidence", 0.25))

        base.MEMORY.append(sid, "user", text, {"intent": "structured_mcq"})
        base.MEMORY.append(
            sid,
            "assistant",
            reply,
            {
                "intent": "structured_mcq",
                "verdict": verdict,
                "decision_source": result.get("decision_source"),
            },
        )

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
                "mcq-reason",
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
            },
            "status": self.status(),
        }


CORE = FAPV8725()
v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v12.Handler):
    server_version = "FAPV87.25SR"


def main() -> None:
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print(f"FAP V{VERSION} Structured Reasoning Gateway")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("New lane: explicit A-D MCQ -> instruction separation -> reasoning -> answer contract")
    print("Compatibility: all non-MCQ requests delegate to V87.12 unchanged")
    print("V87.24 offline bundle and all prior media paths remain unchanged")
    print(f"Optional teacher: {base.OLLAMA_MODEL} @ {base.OLLAMA_BASE} (fallback={base.TEACHER_FALLBACK})")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
