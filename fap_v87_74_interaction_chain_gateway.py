#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_73_exponential_linear_gateway as v73
from fap_interaction_chain import (
    HandoffPolicy,
    InteractionChainCoordinator,
    InteractionChainResult,
)
from fap_interaction_fabric import InteractionRequest

base = v73.base
VERSION = "87.74-unified-chat"


class FAPV8774Unified(v73.FAPV8773Unified):
    """V87.73 plus explicit bounded cooperative endpoint handoff."""

    def __init__(self):
        super().__init__()
        self.interaction_chain = InteractionChainCoordinator(
            self.interactions,
            max_steps=12,
            allow_revisit=False,
            max_history_turns=128,
        )

    def run_interaction_chain(
        self,
        initial: InteractionRequest,
        policy: HandoffPolicy,
    ) -> InteractionChainResult:
        return self.interaction_chain.run(initial, policy)

    def chain_from_chat(
        self,
        text: str,
        history: list[dict],
        policy: HandoffPolicy,
        *,
        intent=None,
        pressure_hint: float = 0.0,
    ) -> InteractionChainResult:
        request = InteractionRequest(
            text=text,
            history=tuple(history or ()),
            channel="chat",
            pressure_hint=pressure_hint,
            metadata={"intent": intent},
        )
        return self.run_interaction_chain(request, policy)

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.74",
            "bounded-cooperative-interaction-chain",
            "explicit-handoff-policy",
            "endpoint-allowlist-handoff",
            "no-endpoint-revisit-by-default",
            "exponential-linear-chain-step-budget",
            "chat-reasoning-code-verification-composable",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.74",
                "interaction_chain": {
                    "enabled": True,
                    "contract": self.interaction_chain.CONTRACT,
                    "max_steps": self.interaction_chain.max_steps,
                    "allow_revisit": self.interaction_chain.allow_revisit,
                    "max_history_turns": self.interaction_chain.max_history_turns,
                    "automatic_default_chat_chaining": False,
                    "handoff_policy_required": True,
                    "fca_required": False,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8774Unified()
v73.CORE = CORE
v73.v64.CORE = CORE
v73.v64.v63.CORE = CORE
v73.v64.v63.v62.CORE = CORE
v73.v64.v63.v62.v61.CORE = CORE
v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v73.Handler):
    server_version = "FAPV87.74InteractionChain"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.74",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.74 COOPERATIVE INTERACTION CHAIN")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Default chat remains single-route unless a host explicitly supplies a handoff policy.")
    print("Chain safety: bounded steps, optional allowlists, no endpoint revisit by default.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
