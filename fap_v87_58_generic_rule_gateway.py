#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_57_generic_derivation_gateway as v57
from fap_generic_rule_reasoner import GenericRuleReasoner

base = v57.base
VERSION = "87.58-unified-chat"


class FAPV8758Unified(v57.FAPV8757Unified):
    """V87.57 plus generic semantic rule chaining.

    Natural-language aliases, subjects, constants, and inference rules live in
    JSONL data. This gateway has no question-specific answer branch.
    """

    def __init__(self):
        super().__init__()
        self.rule_reasoner = GenericRuleReasoner(base.ROOT)

    def route(self, intent, text: str, history: list[dict]) -> dict:
        ruled = self.rule_reasoner.run(text, history)
        if ruled is not None:
            return ruled
        return super().route(intent, text, history)

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.58",
            "generic-semantic-rule-chaining",
            "context-subject-resolution",
            "recursive-derived-relations",
            "safe-data-driven-expression-eval",
            "evidence-trace",
            "no-question-specific-answer-branches",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.58",
            "generic_rule_reasoner": {
                "enabled": True,
                "entities": len(self.rule_reasoner.entities),
                "relations": len(self.rule_reasoner.relations),
                "rules": len(self.rule_reasoner.rules),
                "constants": len(self.rule_reasoner.constants),
                "knowledge_as_data": True,
                "question_specific_answer_branches": False,
                "context_subject_resolution": True,
                "recursive_rule_chaining": True,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8758Unified()
v57.CORE = CORE
v57.v56.CORE = CORE
v57.v56.v55.CORE = CORE
v57.v56.v55.v54.CORE = CORE
v57.v56.v55.v54.v53.CORE = CORE
v57.v56.v55.v54.v53.v52.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v57.Handler):
    server_version = "FAPV87.58GenericRuleReasoning"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.58",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.58 GENERIC RULE REASONING")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Flow: relation resolve -> context subject resolve -> recursive rule chain -> safe evaluation -> evidence trace")
    print("Question-specific answer branches: none")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
