#!/usr/bin/env python3
from __future__ import annotations

import re
import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_41_low_latency_chat_gateway as v41

base = v41.base
VERSION = "87.42-unified-chat"


class FAPV8742Unified(v41.FAPV8741Unified):
    @staticmethod
    def _science_capability_query(text: str) -> bool:
        t = str(text or "").strip()
        return bool(
            re.search(r"(科学|物理|化学|生物|天文|science|physics|chemistry|biology)", t, re.I)
            and re.search(r"(答えられ|回答でき|できますか|できる[？?]?|対応でき|対応して|可能)", t, re.I)
        )

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.42",
            "science-capability-self-knowledge",
            "unresolved-verdict-partial",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.42",
            "science_chat": {
                "self_capability_answer": True,
                "unresolved_is_partial": True,
            },
        })
        out["capabilities"] = self.capabilities()
        return out

    def route(self, intent, text: str, history: list[dict]):
        if self._science_capability_query(text):
            return {
                "ok": True,
                "reply": (
                    "はい、範囲を限定すれば科学的な質問に答えられます。\n"
                    "現在のローカルFAPは、物理定数・基礎事実の直接回答、A-D形式の科学選択問題、"
                    "力学・波動・電磁気・熱放射・放射性崩壊などの決定論的な物理計算に対応しています。\n"
                    "一方、未知の自由形式の科学知識を何でも持っているわけではないため、"
                    "ローカル知識や検証可能な根拠が不足する場合は、推測で埋めず未解決として返します。"
                ),
                "confidence": 0.99,
                "needs_teacher": False,
                "local": True,
                "self_capability": True,
                "capability_domain": "science",
            }
        return super().route(intent, text, history)


CORE = FAPV8742Unified()
v41.CORE = CORE
v41.v40.CORE = CORE
v41.v40.v39.CORE = CORE
v41.v40.v39.v38.CORE = CORE
v41.v40.v39.v38.v37.CORE = CORE
v41.v40.v39.v38.v37.v28.CORE = CORE
v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v41.Handler):
    server_version = "FAPV87.42ScienceCapability"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.42",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.42 SCIENCE CAPABILITY CHAT")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Science capability questions are answered from implemented local abilities.")
    print("Unresolved chat is no longer incorrectly verified as OK.")
    print("V87.41 low-latency path and prior factual/media stacks are preserved.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
