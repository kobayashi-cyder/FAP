#!/usr/bin/env python3
from __future__ import annotations

import sys
import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_40_factual_chat_gateway as v40

base = v40.base
VERSION = "87.41-unified-chat"


class FAPV8741Unified(v40.FAPV8740Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.41",
            "lightweight-chat-status",
            "fast-ui-status",
            "latency-feedback-conversation",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.41",
            "latency_path": {
                "chat_status_lightweight": True,
                "ui_status_lightweight": True,
                "full_status_endpoint": "/api/v1/status/full",
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8741Unified()
v40.CORE = CORE
v40.v39.CORE = CORE
v40.v39.v38.CORE = CORE
v40.v39.v38.v37.CORE = CORE
v40.v39.v38.v37.v28.CORE = CORE
v40.v39.v38.v37.v28.v27.CORE = CORE
v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v40.Handler):
    server_version = "FAPV87.41LowLatencyChat"

    @classmethod
    def _fast_status(cls):
        module = sys.modules.get(cls.__module__)
        current = str(getattr(module, "VERSION", base.VERSION))
        mainline = current.split("-", 1)[0]
        return {
            "name": "FAP",
            "version": current,
            "mainline_version": mainline,
            "state": "ready",
            "protocol": "1.0",
            "capabilities": [
                "chat",
                "direct-factual-qa",
                "semantic-memory",
                "structured-reasoning",
                "physics-reasoning",
                "image-routing",
                "sparse-media",
                "native-geometry",
                "lightweight-chat-status",
            ],
        }

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.41",
                "state": "ready",
            })
            return
        if path == "/api/v1/status":
            # The UI only needs version/state/capability presence. Avoid the
            # recursive full status tree and optional-service probes here.
            self.send_json(self._fast_status())
            return
        if path == "/api/v1/status/full":
            self.send_json(CORE.status())
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.41 LOW-LATENCY CHAT")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Chat responses use lightweight status; full diagnostics are /api/v1/status/full.")
    print("Latency feedback is handled as ordinary conversation.")
    print("V87.40 factual routing and V87.39 native media stack preserved.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
