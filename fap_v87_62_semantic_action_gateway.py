#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_61_generic_recommendation_gateway as v61
from fap_semantic_action_router import SemanticActionRouter

base = v61.base
VERSION = "87.62-unified-chat"


class FAPV8762Unified(v61.FAPV8761Unified):
    """V87.61 plus data-driven action/resource routing."""

    def __init__(self):
        super().__init__()
        self.semantic_action = SemanticActionRouter(base.ROOT)

    def route(self, intent, text: str, history: list[dict]) -> dict:
        matched = self.semantic_action.match(text)
        if matched is not None:
            route = str(matched.get("route") or "")
            if route == "image_generate":
                result = dict(self.image.run_generate(text))
            elif route == "image_capability":
                result = dict(self.image.run_capability())
            else:
                result = {}
            if result:
                result["semantic_action"] = True
                result["semantic_action_match"] = matched
                result["ability_override"] = route
                tags = list(result.get("route_tags", []))
                for tag in (
                    "semantic-action-resolve",
                    f"resource:{matched.get('resource_id')}",
                    f"action:{matched.get('action_id')}",
                    route,
                ):
                    if tag and tag not in tags:
                        tags.append(tag)
                result["route_tags"] = tags
                return result
        return super().route(intent, text, history)

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.62",
            "semantic-action-router",
            "data-driven-resource-action-composition",
            "paraphrase-stable-image-intent",
            "no-subject-specific-image-routing",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.62",
            "semantic_action_router": {
                "enabled": True,
                "resources": len(self.semantic_action.resources),
                "actions": len(self.semantic_action.actions),
                "rules": len(self.semantic_action.rules),
                "knowledge_as_data": True,
                "subject_specific_branches": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8762Unified()
v61.CORE = CORE
v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v61.Handler):
    server_version = "FAPV87.62SemanticAction"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.62",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.62 SEMANTIC ACTION ROUTING")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Flow: resource concept -> action concept -> route -> organ -> verify")
    print("Subject-specific image routing: none")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
