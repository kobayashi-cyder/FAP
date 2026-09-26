from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any, Mapping, Sequence

from fap_interaction_fabric import InteractionEndpoint, InteractionFabric, InteractionRequest

VERSION = "1.0.01-unified-chat"
MAINLINE_VERSION = "1.0.01"
_ARITHMETIC = re.compile(r"^[0-9eE+*/().\s-]+$")
_SELF = re.compile(r"(?:^|\b)fap(?:\b|$)|バージョン|version|状態|status|能力|capabilit", re.I)
_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
           ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def _safe_number(node: ast.AST, depth: int = 0) -> float:
    if depth > 16:
        raise ValueError("expression too deep")
    if isinstance(node, ast.Expression):
        return _safe_number(node.body, depth + 1)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        value = float(node.value)
    elif isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left = _safe_number(node.left, depth + 1)
        right = _safe_number(node.right, depth + 1)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise ValueError("exponent too large")
        value = _BINOPS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        value = _UNARY[type(node.op)](_safe_number(node.operand, depth + 1))
    else:
        raise ValueError("unsupported arithmetic")
    if not math.isfinite(value) or abs(value) > 1e100:
        raise ValueError("non-finite or oversized result")
    return value

def _arithmetic(text: str) -> str:
    value = str(text or "").strip()
    if not value or len(value) > 160 or not _ARITHMETIC.fullmatch(value):
        raise ValueError("not arithmetic")
    result = _safe_number(ast.parse(value, mode="eval"))
    return str(int(result)) if result.is_integer() else format(result, ".12g")

class FAP1xCore:
    def __init__(self) -> None:
        self.fabric = InteractionFabric()
        self.verified_turns = 0
        self.failed_turns = 0
        self.fabric.register(InteractionEndpoint(
            endpoint_id="arithmetic", channels=("chat",),
            probe=lambda r: 0.98 if _ARITHMETIC.fullmatch(str(r.text or "").strip()) else 0.0,
            handler=self._handle_arithmetic, priority=1.0, cost=0.35,
            capabilities=("arithmetic","verification"), task_families=("math","chat"),
            task_forms=("numeric",)))
        self.fabric.register(InteractionEndpoint(
            endpoint_id="self_status", channels=("chat",),
            probe=lambda r: 0.92 if _SELF.search(str(r.text or "")) else 0.0,
            handler=self._handle_self, priority=0.9, cost=0.35,
            capabilities=("self-inspection","status"), task_families=("chat",)))
        self.fabric.register(InteractionEndpoint(
            endpoint_id="fail_closed", channels=("chat",),
            probe=lambda r: 0.0 if (_ARITHMETIC.fullmatch(str(r.text or "").strip()) or _SELF.search(str(r.text or ""))) else 0.20, handler=self._handle_fallback,
            priority=0.2, cost=0.25, capabilities=("safe-fallback",),
            task_families=("chat",)))

    @staticmethod
    def _handle_arithmetic(request, budget):
        try:
            reply = _arithmetic(request.text)
        except Exception:
            return {"ok": False, "reply": "計算式を安全に評価できませんでした。", "confidence": 0.0}
        return {"ok": True, "reply": reply, "confidence": 0.99, "local": True}

    def _handle_self(self, request, budget):
        return {"ok": True,
                "reply": "FAP 1.0.01 public coreです。1.x系の検証済み能力だけをactive runtimeとして扱います。",
                "confidence": 0.96, "status": self.chat_status(), "local": True}

    @staticmethod
    def _handle_fallback(request, budget):
        return {"ok": False,
                "reply": "このローカル1.xコアだけでは確定回答できません。追加の知識・ツールまたは検証済みendpointが必要です。",
                "confidence": 0.20, "needs_tool": True, "local": True}

    def register_endpoint(self, endpoint: InteractionEndpoint) -> None:
        self.fabric.register(endpoint)

    def chat_result(self, text: str, *, history: Sequence[Mapping[str, Any]] = (),
                    metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self.fabric.dispatch(InteractionRequest(
            text=str(text or ""), history=tuple(history), channel="chat", metadata=metadata)).to_dict()

    def chat(self, text: str) -> str:
        payload = self.chat_result(text).get("payload") or {}
        return str(payload.get("reply", ""))

    def verify(self, query: str, answer: str, success: bool) -> dict[str, Any]:
        if success: self.verified_turns += 1
        else: self.failed_turns += 1
        return {"accepted": True, "success": bool(success),
                "verified_turns": self.verified_turns, "failed_turns": self.failed_turns}

    def capabilities(self) -> list[str]:
        return ["public-mainline:1.0.01","dynamic-sparse-interaction-routing",
                "bounded-adaptive-compute","safe-local-arithmetic","fail-closed-unknowns",
                "speech-adapter-compatible","android-adapter-compatible",
                "native-cpp-alternate-core","isolated-self-improvement-candidate"]

    def chat_status(self) -> dict[str, Any]:
        return {"version": VERSION, "mainline_version": MAINLINE_VERSION,
                "runtime": "fap_runtime_1x", "legacy_version_dependencies": False,
                "endpoints": list(self.fabric.endpoint_ids),
                "dynamic_sparse_routing": {"enabled": True,
                    "interaction_fabric_integrated": True,
                    "mechanism_benchmark_available": True},
                "verification": {"verified_turns": self.verified_turns,
                    "failed_turns": self.failed_turns},
                "intelligence_target": {"target": "GPT-5.6-Sol-class",
                    "target_is_claimed_achieved": False,
                    "task_intelligence_benchmark_complete": False},
                "capabilities": self.capabilities()}

CORE = FAP1xCore()
def chat(text: str) -> str: return CORE.chat(text)
def chat_status() -> dict[str, Any]: return CORE.chat_status()
