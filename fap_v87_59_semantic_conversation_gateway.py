#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_58_generic_rule_gateway as v58
from fap_semantic_conversation import RuntimeSelfProfile, SemanticConversationRouter

base = v58.base
VERSION = "87.59-unified-chat"


class FAPV8759Unified(v58.FAPV8758Unified):
    """V87.58 plus data-driven semantic ordinary-conversation routing."""

    def __init__(self):
        super().__init__()
        self.semantic_conversation = SemanticConversationRouter(base.ROOT)
        self.runtime_profile = RuntimeSelfProfile(self.semantic_conversation)
        self._profile_capabilities_cache: tuple[str, ...] | None = None

    def _profile_capabilities(self) -> tuple[str, ...]:
        if self._profile_capabilities_cache is None:
            self._profile_capabilities_cache = tuple(self.capabilities())
        return self._profile_capabilities_cache

    def route(self, intent, text: str, history: list[dict]) -> dict:
        semantic = self.semantic_conversation.match(text)
        if semantic is not None:
            mode = str(semantic.get("response_mode") or "")
            caps = () if mode == "runtime_greeting" else self._profile_capabilities()
            runtime_status = self.status()
            runtime_version = str(runtime_status.get("version") or VERSION)
            result = self.runtime_profile.run(
                text,
                version=runtime_version,
                capabilities=caps,
                status=self.chat_status(),
            )
            if result is not None:
                return result
        return super().route(intent, text, history)

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.59",
            "semantic-conversation-intents",
            "paraphrase-stable-self-profile",
            "runtime-derived-self-description",
            "data-driven-conversation-routing",
            "dynamic-greeting",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.59",
            "semantic_conversation": {
                "enabled": True,
                "intent_count": len(self.semantic_conversation.intents),
                "capability_groups": len(self.semantic_conversation.groups),
                "knowledge_as_data": True,
                "utterance_specific_router_branches": False,
                "runtime_self_description": True,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8759Unified()
v58.CORE = CORE
v58.v57.CORE = CORE
v58.v57.v56.CORE = CORE
v58.v57.v56.v55.CORE = CORE
v58.v57.v56.v55.v54.CORE = CORE
v58.v57.v56.v55.v54.v53.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v58.v57.v56.v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v58.Handler):
    server_version = "FAPV87.59SemanticConversation"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.59",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.59 SEMANTIC CONVERSATION")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Flow: semantic intent data -> compositional match -> runtime self inspection -> dynamic response")
    print("Utterance-specific router branches: none")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
