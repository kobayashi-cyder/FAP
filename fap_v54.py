#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, re

MEMORY_FILE = Path(__file__).with_name("fap_memory.json")
NEG = ("ない","ません","ではない","じゃない","不可能","誤り","禁止","不可")
STOP = {"の","に","は","を","が","と","で","て","も","へ","や","から","まで","より","です","ます","する","した","して","いる","ある","これ","それ","この","その","こと","もの","何","どう"}

@dataclass
class MemoryItem:
    text: str
    weight: float = 1.0
    source: str = "memory"

@dataclass
class OrganResult:
    organ: str
    confidence: float
    payload: dict

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())

def terms(s: str) -> set[str]:
    p = re.findall(r"[a-z0-9_+\-]+|[一-龥ぁ-んァ-ンー]{2,}", normalize(s))
    return {x for x in p if x not in STOP and len(x) > 1}

def chargrams(s: str, n: int = 2) -> set[str]:
    s = re.sub(r"[\s、。,.!?！？]", "", normalize(s))
    return {s[i:i+n] for i in range(max(0, len(s)-n+1))}

def similarity(a: str, b: str) -> float:
    ta, tb = terms(a), terms(b)
    tok = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
    ga, gb = chargrams(a), chargrams(b)
    ch = len(ga & gb) / len(ga | gb) if ga and gb else 0.0
    return max(tok, ch * 0.82)

def polarity(s: str) -> int:
    x = normalize(s)
    return -1 if any(n in x for n in NEG) else 1

class RetrievalOrgan:
    def run(self, query, memory, k=4):
        ranked = []
        for m in memory:
            score = similarity(query, m.text) * max(0.05, m.weight)
            if score > 0.03:
                ranked.append((score, m))
        ranked.sort(key=lambda x: x[0], reverse=True)
        hits = [{"text":m.text,"score":round(s,4),"source":m.source} for s,m in ranked[:k]]
        conf = min(1.0, sum(x["score"] for x in hits[:2]))
        return OrganResult("retrieve", conf, {"hits":hits})

class DecompositionOrgan:
    SPLIT = re.compile(r"(?:[。！？?!\n]+|(?:そして|また|ただし|しかし|一方で|そのうえで|それから|なので|つまり)[、, ]*)")
    def run(self, query):
        raw = [x.strip(" 、,") for x in self.SPLIT.split(query) if x.strip(" 、,")]
        if len(raw) == 1 and len(query) >= 36:
            p = re.split(r"(?:して、|し、|ので、|ため、|なら、)", query)
            raw = [x.strip() for x in p if x.strip()]
        goals = raw[:8] or [query.strip()]
        constraints = [x for x in ("最小","高速","低RAM","16GB","必須","禁止","のみ","以内","以上","以下") if x.lower() in query.lower()]
        complexity = min(1.0, 0.18*len(goals) + min(len(query),200)/300)
        return OrganResult("decompose", max(0.35,complexity), {"subgoals":goals,"constraints":constraints,"complexity":round(complexity,3)})

class VerificationOrgan:
    def run(self, query, claims):
        claims = [c for c in claims if c]
        conflicts, support = [], []
        qpol = polarity(query)
        for c in claims:
            sim = similarity(query,c)
            if sim < 0.12: continue
            rec = {"claim":c,"similarity":round(sim,4)}
            (conflicts if polarity(c)!=qpol and sim>=0.20 else support).append(rec)
        for i in range(len(claims)):
            for j in range(i+1,len(claims)):
                sim = similarity(claims[i],claims[j])
                if sim>=0.30 and polarity(claims[i])!=polarity(claims[j]):
                    conflicts.append({"claim":claims[i],"against":claims[j],"similarity":round(sim,4)})
        conf = 0.45 + (min(0.35,max((x["similarity"] for x in support),default=0.0)))
        if conflicts: conf = max(0.15,conf-min(0.30,0.08*len(conflicts)))
        return OrganResult("verify",round(min(1.0,conf),3),{"support":support[:5],"conflicts":conflicts[:5]})

class IntegrationOrgan:
    def run(self, query, retrieved, decomposed, verified):
        hits = retrieved.payload.get("hits",[])
        goals = decomposed.payload.get("subgoals",[query])
        conflicts = verified.payload.get("conflicts",[])
        evidence = [h["text"] for h in hits if h["score"]>=0.08]
        stance = "conflict" if conflicts else ("grounded" if evidence else "open")
        frame = {"topic":query.strip(),"subgoals":goals,"evidence":evidence[:4],"conflicts":conflicts[:3],"stance":stance}
        conf = 0.30 + (min(0.45,retrieved.confidence*0.6) if evidence else 0) + (0.08 if len(goals)>1 else 0)
        if conflicts: conf -= min(0.18,0.06*len(conflicts))
        return OrganResult("integrate",round(max(0.1,min(0.95,conf)),3),frame)

class FAPV39:
    def __init__(self):
        self.retrieve=RetrievalOrgan(); self.decompose=DecompositionOrgan(); self.verify=VerificationOrgan(); self.integrate=IntegrationOrgan()
        self.memory=[]; self.recent=[]; self.load_memory()

    def load_memory(self):
        if not MEMORY_FILE.exists(): return
        try:
            self.memory=[MemoryItem(**x) for x in json.loads(MEMORY_FILE.read_text(encoding="utf-8")) if x.get("text")]
        except Exception:
            self.memory=[]

    def save_memory(self):
        MEMORY_FILE.write_text(json.dumps([asdict(x) for x in self.memory[-1000:]],ensure_ascii=False,indent=2),encoding="utf-8")

    def learn(self,text,weight=1.0,source="user"):
        text=text.strip()
        if text:
            self.memory.append(MemoryItem(text,float(weight),source)); self.save_memory()

    def route(self,query):
        d=self.decompose.run(query)
        r=self.retrieve.run(query,self.memory+[MemoryItem(x,0.35,"recent") for x in self.recent])
        c,known=d.payload["complexity"],r.confidence
        if c<0.30 and known>=0.35: return ["retrieve","verify","integrate"]
        if c<0.38 and known<0.20: return ["decompose","retrieve","integrate"]
        return ["decompose","retrieve","verify","integrate"]

    def think(self,query):
        route=self.route(query)
        d=self.decompose.run(query)
        r=self.retrieve.run(query,self.memory+[MemoryItem(x,0.35,"recent") for x in self.recent])
        claims=[h["text"] for h in r.payload.get("hits",[])]
        v=self.verify.run(query,claims) if "verify" in route else OrganResult("verify",0.25,{"support":[],"conflicts":[]})
        i=self.integrate.run(query,r,d,v)
        self.recent=(self.recent+[query])[-12:]
        return {"version":"V39","route":route,"confidence":i.confidence,"frame":i.payload,
                "organs":{"retrieve":asdict(r),"decompose":asdict(d),"verify":asdict(v),"integrate":asdict(i)}}

    def verbalize(self,state):
        f=state["frame"]; goals=f["subgoals"]; ev=f["evidence"]; conflicts=f["conflicts"]
        if conflicts: head="記憶内に矛盾候補があります。断定せず、まず矛盾を解消します。"
        elif ev: head="関連する記憶を取り出し、分解して統合しました。"
        else: head="内部記憶だけでは根拠が足りません。問題構造までは分解できますが、事実の補完が必要です。"
        parts=[head]
        if len(goals)>1: parts.append("論点: "+" / ".join(goals[:5]))
        if ev: parts.append("根拠候補: "+" / ".join(ev[:3]))
        parts.append("経路: "+" → ".join(state["route"]))
        parts.append(f"統合信頼度: {state['confidence']:.2f}")
        return "\n".join(parts)

def main():
    fap=FAPV39()
    print("FAP V39 REAL ORGANS MINIMAL")
    print("commands: :learn <text> | :json <question> | :quit")
    while True:
        try: q=input("\nYou> ").strip()
        except (EOFError,KeyboardInterrupt): print(); break
        if not q: continue
        if q in (":q",":quit","exit","quit"): break
        if q.startswith(":learn "): fap.learn(q[7:]); print("FAP> learned"); continue
        if q.startswith(":json "): print(json.dumps(fap.think(q[6:]),ensure_ascii=False,indent=2)); continue
        st=fap.think(q); print("FAP> "+fap.verbalize(st))


# ============================================================
# FAP V40 - Recursive Cognitive Loop Controller
# ============================================================

@dataclass
class LoopStep:
    cycle: int
    action: str
    confidence_before: float
    confidence_after: float
    improvement: float
    reason: str

class RecursiveController:
    """
    Decides whether another cognitive pass is worth spending.
    This is intentionally small and deterministic:
      - conflict -> verify/retrieve again
      - weak evidence -> retrieve again
      - complex/underspecified -> decompose again
      - otherwise -> integrate and stop
    """

    def __init__(self, max_cycles: int = 4, min_improvement: float = 0.025):
        self.max_cycles = max(1, int(max_cycles))
        self.min_improvement = max(0.0, float(min_improvement))

    def choose_action(self, state: dict) -> tuple[str, str]:
        organs = state["organs"]
        frame = state["frame"]

        conflicts = frame.get("conflicts", [])
        evidence = frame.get("evidence", [])
        complexity = organs["decompose"]["payload"].get("complexity", 0.0)
        rconf = organs["retrieve"]["confidence"]
        iconf = state["confidence"]

        if conflicts:
            return "verify_again", "矛盾候補が残っている"
        if not evidence or rconf < 0.22:
            return "retrieve_again", "根拠候補が弱い"
        if complexity >= 0.52 and len(frame.get("subgoals", [])) <= 1:
            return "decompose_again", "問題が複雑だが分解が不足"
        if iconf < 0.46:
            return "integrate_again", "統合信頼度が低い"
        return "stop", "追加計算の期待利益が小さい"

class FAPV40(FAPV39):
    def __init__(self, max_cycles: int = 4, min_improvement: float = 0.025):
        super().__init__()
        self.controller = RecursiveController(max_cycles, min_improvement)

    def _re_retrieve(self, query: str, state: dict):
        """
        Broaden retrieval by using subgoals as alternate probes and merging hits.
        """
        mem = self.memory + [MemoryItem(x, 0.35, "recent") for x in self.recent]
        probes = [query] + state["frame"].get("subgoals", [])[:4]

        merged = {}
        for probe in probes:
            rr = self.retrieve.run(probe, mem, k=6)
            for h in rr.payload.get("hits", []):
                key = h["text"]
                # Reward hits that appear under more than one probe.
                if key in merged:
                    merged[key]["score"] = min(1.0, merged[key]["score"] + h["score"] * 0.20)
                else:
                    merged[key] = dict(h)

        hits = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:6]
        conf = min(1.0, sum(x["score"] for x in hits[:3]))
        state["organs"]["retrieve"] = asdict(OrganResult("retrieve", conf, {"hits": hits}))

    def _re_decompose(self, query: str, state: dict):
        """
        Second-pass decomposition: combine punctuation and coordination clues.
        """
        existing = state["frame"].get("subgoals", [])
        candidates = []

        chunks = re.split(
            r"(?:[。！？?!\n]+|、(?:さらに|また|ただし|しかし|そして)?|(?:そして|また|ただし|しかし|その後|最後に))",
            query
        )
        for x in chunks:
            x = x.strip(" 、,")
            if len(x) >= 4:
                candidates.append(x)

        # Preserve old goals, add novel ones only.
        goals = []
        seen = set()
        for x in existing + candidates:
            k = normalize(x)
            if k and k not in seen:
                seen.add(k)
                goals.append(x)

        if not goals:
            goals = [query.strip()]

        old = state["organs"]["decompose"]
        payload = dict(old["payload"])
        payload["subgoals"] = goals[:8]
        payload["complexity"] = round(
            min(1.0, max(payload.get("complexity", 0.0), 0.16 * len(goals) + min(len(query), 240) / 320)),
            3
        )
        state["organs"]["decompose"] = asdict(
            OrganResult("decompose", max(old["confidence"], 0.45), payload)
        )

    def _re_verify(self, query: str, state: dict):
        hits = state["organs"]["retrieve"]["payload"].get("hits", [])
        claims = [h["text"] for h in hits]
        v = self.verify.run(query, claims)

        # If support dominates conflicts, slightly increase confidence.
        if len(v.payload.get("support", [])) > len(v.payload.get("conflicts", [])):
            v.confidence = min(1.0, v.confidence + 0.05)

        state["organs"]["verify"] = asdict(v)

    def _re_integrate(self, query: str, state: dict):
        r = state["organs"]["retrieve"]
        d = state["organs"]["decompose"]
        v = state["organs"]["verify"]

        rr = OrganResult(r["organ"], r["confidence"], r["payload"])
        dd = OrganResult(d["organ"], d["confidence"], d["payload"])
        vv = OrganResult(v["organ"], v["confidence"], v["payload"])
        ii = self.integrate.run(query, rr, dd, vv)

        # Recursion bonus is tiny and only applies when evidence is present and no conflicts remain.
        if ii.payload.get("evidence") and not ii.payload.get("conflicts"):
            ii.confidence = round(min(0.97, ii.confidence + 0.025), 3)

        state["organs"]["integrate"] = asdict(ii)
        state["frame"] = ii.payload
        state["confidence"] = ii.confidence

    def think_recursive(self, query: str) -> dict:
        state = super().think(query)
        state["version"] = "V40"
        trace = []

        # Always re-integrate from the first state once, so V40 has a stable baseline.
        self._re_integrate(query, state)

        for cycle in range(1, self.controller.max_cycles + 1):
            before = float(state["confidence"])
            action, reason = self.controller.choose_action(state)

            if action == "stop":
                trace.append(asdict(LoopStep(
                    cycle=cycle,
                    action="stop",
                    confidence_before=before,
                    confidence_after=before,
                    improvement=0.0,
                    reason=reason,
                )))
                break

            if action == "retrieve_again":
                self._re_retrieve(query, state)
                self._re_verify(query, state)
                self._re_integrate(query, state)

            elif action == "decompose_again":
                self._re_decompose(query, state)
                self._re_retrieve(query, state)
                self._re_verify(query, state)
                self._re_integrate(query, state)

            elif action == "verify_again":
                self._re_verify(query, state)
                self._re_integrate(query, state)

            elif action == "integrate_again":
                self._re_integrate(query, state)

            after = float(state["confidence"])
            improvement = round(after - before, 4)
            trace.append(asdict(LoopStep(
                cycle=cycle,
                action=action,
                confidence_before=round(before, 4),
                confidence_after=round(after, 4),
                improvement=improvement,
                reason=reason,
            )))

            # Diminishing-return stop: no useful gain after a completed pass.
            if improvement < self.controller.min_improvement:
                trace.append(asdict(LoopStep(
                    cycle=cycle,
                    action="stop",
                    confidence_before=round(after, 4),
                    confidence_after=round(after, 4),
                    improvement=0.0,
                    reason="改善量が閾値未満",
                )))
                break

        state["loop_trace"] = trace
        state["cycles_used"] = sum(1 for x in trace if x["action"] != "stop")
        return state

    def verbalize_recursive(self, state: dict) -> str:
        base = self.verbalize(state)
        trace = state.get("loop_trace", [])
        actions = [x["action"] for x in trace if x["action"] != "stop"]
        if actions:
            return base + "\n再思考: " + " → ".join(actions) + f"\n再思考回数: {state.get('cycles_used', 0)}"
        return base + "\n再思考: 不要"

def main_v40():
    fap = FAPV40()
    print("FAP V40 RECURSIVE ORGANS MINIMAL")
    print("commands: :learn <text> | :json <question> | :quit")
    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break
        if q.startswith(":learn "):
            fap.learn(q[7:])
            print("FAP> learned")
            continue
        if q.startswith(":json "):
            print(json.dumps(fap.think_recursive(q[6:]), ensure_ascii=False, indent=2))
            continue
        st = fap.think_recursive(q)
        print("FAP> " + fap.verbalize_recursive(st))


# ============================================================
# FAP V41 - CHAT FIRST, REASON SECOND
# ============================================================

@dataclass
class ChatTurn:
    role: str
    text: str

class ConversationState:
    def __init__(self, max_turns: int = 24):
        self.max_turns = max(4, int(max_turns))
        self.turns: list[ChatTurn] = []
        self.topic: str = ""
        self.last_user_intent: str = "chat"

    def add(self, role: str, text: str):
        self.turns.append(ChatTurn(role, text.strip()))
        self.turns = self.turns[-self.max_turns:]
        if role == "user":
            self.topic = self._extract_topic(text)
            self.last_user_intent = self._classify_intent(text)

    def _extract_topic(self, text: str) -> str:
        # Minimal deterministic topic extractor.
        t = normalize(text)
        words = re.findall(r"[a-z0-9_+\-]+|[一-龥ぁ-んァ-ンー]{2,}", t)
        filtered = [w for w in words if w not in STOP]
        return " ".join(filtered[:5]) if filtered else text.strip()[:40]

    def _classify_intent(self, text: str) -> str:
        t = text.strip()
        if any(x in t for x in ("なぜ","どうして","理由")):
            return "why"
        if any(x in t for x in ("どう","方法","やり方","手順")):
            return "how"
        if any(x in t for x in ("何","とは","って")):
            return "what"
        if t.endswith(("?","？")):
            return "question"
        if any(x in t for x in ("ありがとう","なるほど","そうですね","わかりました")):
            return "ack"
        return "chat"

    def recent_user_text(self, n: int = 4) -> list[str]:
        xs = [t.text for t in self.turns if t.role == "user"]
        return xs[-n:]

    def compact_context(self) -> str:
        # Keep context sparse: topic + recent user turns only.
        recent = self.recent_user_text(4)
        parts = []
        if self.topic:
            parts.append("現在話題=" + self.topic)
        if recent:
            parts.append("直近=" + " | ".join(recent))
        return " ; ".join(parts)

class ChatPlanner:
    """
    Builds the conversation layer BEFORE inference.
    The planner decides what kind of reply is needed and what should be reasoned about.
    """
    def plan(self, state: ConversationState, user_text: str) -> dict:
        intent = state.last_user_intent
        needs_reasoning = intent in ("why","how","what","question") or len(user_text) >= 16

        if intent == "ack":
            reply_mode = "continuation"
        elif intent == "why":
            reply_mode = "explain_reason"
        elif intent == "how":
            reply_mode = "procedure"
        elif intent == "what":
            reply_mode = "definition"
        elif intent == "question":
            reply_mode = "answer"
        else:
            reply_mode = "conversation"

        reasoning_query = user_text
        ctx = state.compact_context()
        if ctx:
            reasoning_query = f"{user_text}\n[会話文脈] {ctx}"

        return {
            "intent": intent,
            "reply_mode": reply_mode,
            "needs_reasoning": needs_reasoning,
            "reasoning_query": reasoning_query,
        }

class ChatVerbalizer:
    def render(self, user_text: str, plan: dict, reasoning_state: dict | None) -> str:
        mode = plan["reply_mode"]

        if reasoning_state is None:
            if mode == "continuation":
                return "了解しました。前の話題を維持して続けます。"
            return "会話内容を受け取りました。必要なときだけ推論に回します。"

        frame = reasoning_state["frame"]
        evidence = frame.get("evidence", [])
        conflicts = frame.get("conflicts", [])
        subgoals = frame.get("subgoals", [])

        if conflicts:
            core = "内部では矛盾候補が残っています。断定せず、検証を優先します。"
        elif evidence:
            core = "会話履歴と記憶を参照しながら、関連情報を統合しました。"
        else:
            core = "会話文脈は保持していますが、内部記憶だけでは根拠が不足しています。"

        if mode == "procedure":
            head = "手順として整理します。"
        elif mode == "explain_reason":
            head = "理由から整理します。"
        elif mode == "definition":
            head = "まず意味を整理します。"
        elif mode == "answer":
            head = "質問に答えます。"
        else:
            head = "会話の流れを維持して返します。"

        parts = [head, core]

        if len(subgoals) > 1:
            parts.append("論点: " + " / ".join(subgoals[:4]))

        parts.append(
            "内部経路: " + " → ".join(reasoning_state.get("route", []))
            + f" / 再思考 {reasoning_state.get('cycles_used', 0)}回"
        )
        return "\n".join(parts)

class FAPV41(FAPV40):
    def __init__(self, max_cycles: int = 4, min_improvement: float = 0.025):
        super().__init__(max_cycles=max_cycles, min_improvement=min_improvement)
        self.chat = ConversationState()
        self.chat_planner = ChatPlanner()
        self.chat_verbalizer = ChatVerbalizer()

    def chat_once(self, user_text: str) -> dict:
        # 1) chat layer receives input first
        self.chat.add("user", user_text)

        # 2) chat layer decides whether/how to reason
        plan = self.chat_planner.plan(self.chat, user_text)

        # 3) reasoning happens only after chat planning
        reasoning_state = None
        if plan["needs_reasoning"]:
            reasoning_state = self.think_recursive(plan["reasoning_query"])

        # 4) return to chat layer for verbalization
        reply = self.chat_verbalizer.render(user_text, plan, reasoning_state)
        self.chat.add("assistant", reply)

        return {
            "version": "V41",
            "user_text": user_text,
            "topic": self.chat.topic,
            "intent": plan["intent"],
            "reply_mode": plan["reply_mode"],
            "used_reasoning": reasoning_state is not None,
            "reply": reply,
            "reasoning": reasoning_state,
            "conversation_turns": len(self.chat.turns),
        }

def main_v41():
    fap = FAPV41()
    print("FAP V41 CHAT -> REASON -> CHAT")
    print("commands: :learn <text> | :json <text> | :history | :quit")

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break

        if q.startswith(":learn "):
            fap.learn(q[7:])
            print("FAP> learned")
            continue

        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue

        if q.startswith(":json "):
            result = fap.chat_once(q[6:])
            print(json.dumps(result, ensure_ascii=False, indent=2))
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])


# ============================================================
# FAP V42 - RICH CHAT / DETOUR / RETURN / REDUNDANCY CONTROL
# ============================================================

class TopicStack:
    def __init__(self, max_topics: int = 8):
        self.max_topics = max(2, int(max_topics))
        self.stack: list[str] = []

    def push(self, topic: str):
        topic = topic.strip()
        if not topic:
            return
        if self.stack and self.stack[-1] == topic:
            return
        self.stack.append(topic)
        self.stack = self.stack[-self.max_topics:]

    def current(self) -> str:
        return self.stack[-1] if self.stack else ""

    def previous(self) -> str:
        return self.stack[-2] if len(self.stack) >= 2 else ""

    def pop_to_previous(self) -> str:
        if len(self.stack) >= 2:
            self.stack.pop()
        return self.current()

class RichConversationState(ConversationState):
    RETURN_CUES = (
        "話を戻す", "本題に戻る", "戻りましょう", "戻って", "さっきの話",
        "先ほどの話", "元の話", "本題"
    )
    DETOUR_CUES = (
        "ちなみに", "ところで", "余談", "ついでに", "そういえば", "別件"
    )

    def __init__(self, max_turns: int = 40):
        super().__init__(max_turns=max_turns)
        self.topics = TopicStack()
        self.detour_depth = 0
        self.verbosity = "normal"
        self.last_reply_fragments: list[str] = []

    def set_verbosity(self, level: str):
        if level in ("short", "normal", "long"):
            self.verbosity = level

    def add(self, role: str, text: str):
        if role == "user":
            is_return = any(x in text for x in self.RETURN_CUES)
            is_detour = any(x in text for x in self.DETOUR_CUES)

            if is_return:
                restored = self.topics.pop_to_previous()
                if restored:
                    self.topic = restored
                self.detour_depth = max(0, self.detour_depth - 1)
            else:
                new_topic = self._extract_topic(text)
                if new_topic:
                    if is_detour and self.topic:
                        self.detour_depth += 1
                    if not self.topic or similarity(new_topic, self.topic) < 0.16:
                        self.topics.push(new_topic)
                    self.topic = self.topics.current() or new_topic

            self.last_user_intent = self._classify_intent(text)

        self.turns.append(ChatTurn(role, text.strip()))
        self.turns = self.turns[-self.max_turns:]

    def compact_context(self) -> str:
        recent = self.recent_user_text(6)
        parts = []
        if self.topic:
            parts.append("現在話題=" + self.topic)
        prev = self.topics.previous()
        if prev:
            parts.append("前話題=" + prev)
        if self.detour_depth:
            parts.append(f"寄り道深度={self.detour_depth}")
        if recent:
            parts.append("直近=" + " | ".join(recent))
        return " ; ".join(parts)

    def remember_reply(self, text: str):
        frags = [x.strip() for x in re.split(r"[。！？\n]+", text) if x.strip()]
        self.last_reply_fragments = frags[-10:]

    def novelty_filter(self, text: str) -> str:
        """
        Remove near-duplicate sentences compared with the last assistant reply.
        """
        parts = [x.strip() for x in re.split(r"(?<=[。！？])|\n", text) if x.strip()]
        kept = []
        for p in parts:
            if any(similarity(p, old) >= 0.72 for old in self.last_reply_fragments):
                continue
            kept.append(p)
        return "\n".join(kept) if kept else text

class RichChatPlanner(ChatPlanner):
    def plan(self, state: RichConversationState, user_text: str) -> dict:
        p = super().plan(state, user_text)

        is_return = any(x in user_text for x in state.RETURN_CUES)
        is_detour = any(x in user_text for x in state.DETOUR_CUES)

        p["is_return"] = is_return
        p["is_detour"] = is_detour
        p["detour_depth"] = state.detour_depth
        p["verbosity"] = state.verbosity

        # Follow-up pronouns should inherit context and usually require reasoning.
        followup = any(x in user_text for x in ("それ", "その", "これ", "あれ", "さっき", "先ほど"))
        if followup and len(state.turns) >= 2:
            p["needs_reasoning"] = True

        ctx = state.compact_context()
        p["reasoning_query"] = user_text if not ctx else f"{user_text}\n[会話文脈] {ctx}"
        return p

class RichChatVerbalizer(ChatVerbalizer):
    def _limit(self, lines: list[str], verbosity: str) -> list[str]:
        if verbosity == "short":
            return lines[:2]
        if verbosity == "long":
            return lines[:7]
        return lines[:4]

    def render(self, user_text: str, plan: dict, reasoning_state: dict | None, state: RichConversationState) -> str:
        if reasoning_state is None:
            if plan.get("is_return"):
                base = "本題に戻します。"
            elif plan.get("is_detour"):
                base = "その寄り道も会話文脈として保持します。"
            elif plan["reply_mode"] == "continuation":
                base = "前の流れを保ったまま続けます。"
            else:
                base = "会話として受け取りました。必要な部分だけ推論に回します。"

            if state.topic:
                base += f"\n現在の話題: {state.topic}"
            return base

        f = reasoning_state["frame"]
        evidence = f.get("evidence", [])
        conflicts = f.get("conflicts", [])
        subgoals = f.get("subgoals", [])
        cycles = reasoning_state.get("cycles_used", 0)

        lines = []

        if plan.get("is_return"):
            lines.append("本題に戻して整理します。")
        elif plan.get("is_detour"):
            lines.append("寄り道として扱いつつ、元の話題は保持します。")
        elif plan["reply_mode"] == "procedure":
            lines.append("手順として整理します。")
        elif plan["reply_mode"] == "explain_reason":
            lines.append("理由を中心に整理します。")
        elif plan["reply_mode"] == "definition":
            lines.append("まず意味を整理します。")
        else:
            lines.append("会話の流れを保って答えます。")

        if conflicts:
            lines.append("内部では矛盾候補が残っているため、断定より検証を優先します。")
        elif evidence:
            lines.append("会話履歴と内部記憶を参照し、関連情報を統合しました。")
        else:
            lines.append("会話文脈は保持していますが、内部記憶だけでは根拠が十分ではありません。")

        if subgoals:
            if len(subgoals) > 1:
                lines.append("論点: " + " / ".join(subgoals[:5]))
            elif plan["verbosity"] == "long":
                lines.append("中心論点: " + subgoals[0])

        if plan["verbosity"] == "long":
            prev = state.topics.previous()
            if prev and state.detour_depth:
                lines.append(f"元の話題「{prev}」も保持しています。")
            lines.append(
                "内部経路: " + " → ".join(reasoning_state.get("route", []))
                + f" / 再思考 {cycles}回"
            )

        rendered = "\n".join(self._limit(lines, plan["verbosity"]))
        return state.novelty_filter(rendered)

class FAPV42(FAPV40):
    def __init__(self, max_cycles: int = 4, min_improvement: float = 0.025):
        super().__init__(max_cycles=max_cycles, min_improvement=min_improvement)
        self.chat = RichConversationState()
        self.chat_planner = RichChatPlanner()
        self.chat_verbalizer = RichChatVerbalizer()

    def set_verbosity(self, level: str):
        self.chat.set_verbosity(level)

    def chat_once(self, user_text: str) -> dict:
        self.chat.add("user", user_text)
        plan = self.chat_planner.plan(self.chat, user_text)

        reasoning_state = None
        if plan["needs_reasoning"]:
            reasoning_state = self.think_recursive(plan["reasoning_query"])

        reply = self.chat_verbalizer.render(user_text, plan, reasoning_state, self.chat)
        self.chat.add("assistant", reply)
        self.chat.remember_reply(reply)

        return {
            "version": "V42",
            "user_text": user_text,
            "topic": self.chat.topic,
            "previous_topic": self.chat.topics.previous(),
            "detour_depth": self.chat.detour_depth,
            "intent": plan["intent"],
            "reply_mode": plan["reply_mode"],
            "verbosity": plan["verbosity"],
            "used_reasoning": reasoning_state is not None,
            "reply": reply,
            "reasoning": reasoning_state,
            "conversation_turns": len(self.chat.turns),
        }

def main_v42():
    fap = FAPV42()
    print("FAP V42 RICH CHAT -> REASON -> CHAT")
    print("commands: :learn <text> | :json <text> | :history | :short | :normal | :long | :quit")

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break
        if q.startswith(":learn "):
            fap.learn(q[7:])
            print("FAP> learned")
            continue
        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue
        if q in (":short", ":normal", ":long"):
            fap.set_verbosity(q[1:])
            print("FAP> verbosity=" + q[1:])
            continue
        if q.startswith(":json "):
            print(json.dumps(fap.chat_once(q[6:]), ensure_ascii=False, indent=2))
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])


# ============================================================
# FAP V43 - CONCEPT / RELATION LEARNING
# ============================================================

CONCEPT_FILE = Path(__file__).with_name("fap_concepts.json")

@dataclass
class ConceptNode:
    name: str
    count: int = 1
    confidence: float = 0.6

@dataclass
class RelationEdge:
    subject: str
    relation: str
    object: str
    confidence: float = 0.6
    support: int = 1

class ConceptGraph:
    def __init__(self):
        self.nodes: dict[str, ConceptNode] = {}
        self.edges: list[RelationEdge] = []
        self.load()

    def load(self):
        if not CONCEPT_FILE.exists():
            return
        try:
            raw = json.loads(CONCEPT_FILE.read_text(encoding="utf-8"))
            for x in raw.get("nodes", []):
                n = ConceptNode(**x)
                self.nodes[n.name] = n
            self.edges = [RelationEdge(**x) for x in raw.get("edges", [])]
        except Exception:
            self.nodes = {}
            self.edges = []

    def save(self):
        data = {
            "nodes": [asdict(x) for x in self.nodes.values()],
            "edges": [asdict(x) for x in self.edges[-2000:]],
        }
        CONCEPT_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _touch_node(self, name: str, confidence: float):
        name = name.strip()
        if not name:
            return
        if name in self.nodes:
            n = self.nodes[name]
            n.count += 1
            n.confidence = min(0.98, (n.confidence * 0.85) + (confidence * 0.15))
        else:
            self.nodes[name] = ConceptNode(name=name, count=1, confidence=confidence)

    def add_relation(self, subject: str, relation: str, obj: str, confidence: float):
        subject, relation, obj = subject.strip(), relation.strip(), obj.strip()
        if not subject or not relation or not obj:
            return False

        self._touch_node(subject, confidence)
        self._touch_node(obj, confidence)

        for e in self.edges:
            if e.subject == subject and e.relation == relation and e.object == obj:
                e.support += 1
                e.confidence = min(0.99, e.confidence + 0.05 * (1.0 - e.confidence))
                self.save()
                return True

        self.edges.append(RelationEdge(subject, relation, obj, confidence, 1))
        self.save()
        return True

    def query(self, text: str, k: int = 6) -> list[dict]:
        hits = []
        for e in self.edges:
            probe = f"{e.subject} {e.relation} {e.object}"
            s = similarity(text, probe)
            if s > 0.08:
                hits.append({
                    "subject": e.subject,
                    "relation": e.relation,
                    "object": e.object,
                    "confidence": round(e.confidence, 3),
                    "score": round(s, 4),
                    "support": e.support,
                })
        hits.sort(key=lambda x: (x["score"] * x["confidence"], x["support"]), reverse=True)
        return hits[:k]

class FactExtractor:
    """
    Conservative, deterministic extractor.
    Learns only short declarative relations from user statements.
    """
    COPULA = re.compile(
        r"^\s*(?P<s>.{1,40}?)\s*(?:は|が)\s*(?P<o>.{1,80}?)(?:です|である|だ)?[。.]?\s*$"
    )
    HAS = re.compile(
        r"^\s*(?P<s>.{1,40}?)\s*(?:には|は)\s*(?P<o>.{1,80}?)(?:がある|を持つ|が存在する)[。.]?\s*$"
    )

    UNSAFE_CUES = (
        "たぶん","多分","かも","かもしれない","と思う","気がする",
        "もし","仮に","例えば","例として","？","?"
    )

    def extract(self, text: str) -> list[tuple[str,str,str,float]]:
        text = text.strip()
        if not text or len(text) > 180:
            return []
        if any(x in text for x in self.UNSAFE_CUES):
            return []

        out = []

        m = self.HAS.match(text)
        if m:
            s = m.group("s").strip()
            o = m.group("o").strip()
            if 1 <= len(s) <= 40 and 1 <= len(o) <= 80:
                out.append((s, "has", o, 0.72))
            return out

        m = self.COPULA.match(text)
        if m:
            s = m.group("s").strip()
            o = m.group("o").strip()

            # Reject obvious command/request language.
            if any(x in o for x in ("してください","してほしい","お願いします","できますか","でしょうか")):
                return []

            # Relation choice: "is" by default.
            if 1 <= len(s) <= 40 and 1 <= len(o) <= 80:
                out.append((s, "is", o, 0.68))

        return out

class LearningGate:
    """
    Prevents noisy or unverified content from entering long-term concept memory.
    """
    def allow_user_fact(self, text: str, extracted) -> bool:
        if not extracted:
            return False
        if len(text.strip()) < 4:
            return False
        return True

    def allow_reasoned_fact(self, reasoning_state: dict | None) -> bool:
        if not reasoning_state:
            return False
        frame = reasoning_state.get("frame", {})
        conflicts = frame.get("conflicts", [])
        evidence = frame.get("evidence", [])
        conf = reasoning_state.get("confidence", 0.0)
        return (not conflicts) and bool(evidence) and conf >= 0.62

class FAPV43(FAPV42):
    def __init__(self, max_cycles: int = 4, min_improvement: float = 0.025):
        super().__init__(max_cycles=max_cycles, min_improvement=min_improvement)
        self.concepts = ConceptGraph()
        self.fact_extractor = FactExtractor()
        self.learning_gate = LearningGate()

    def _inject_concepts(self, user_text: str) -> str:
        hits = self.concepts.query(user_text, k=4)
        if not hits:
            return user_text

        facts = []
        for h in hits:
            rel = h["relation"]
            if rel == "is":
                facts.append(f'{h["subject"]} は {h["object"]}')
            elif rel == "has":
                facts.append(f'{h["subject"]} には {h["object"]} がある')
            else:
                facts.append(f'{h["subject"]} {rel} {h["object"]}')

        return user_text + "\n[学習済み概念] " + " / ".join(facts)

    def _learn_from_user(self, user_text: str) -> list[dict]:
        extracted = self.fact_extractor.extract(user_text)
        learned = []

        if not self.learning_gate.allow_user_fact(user_text, extracted):
            return learned

        for s, r, o, c in extracted:
            if self.concepts.add_relation(s, r, o, c):
                learned.append({
                    "subject": s,
                    "relation": r,
                    "object": o,
                    "confidence": c,
                })
                # Also expose as ordinary memory for V40 retrieval.
                self.learn(f"{s} {r} {o}", weight=c, source="concept")

        return learned

    def chat_once(self, user_text: str) -> dict:
        # Learn explicit user facts first.
        learned = self._learn_from_user(user_text)

        # Conversation still comes before reasoning.
        self.chat.add("user", user_text)
        plan = self.chat_planner.plan(self.chat, user_text)

        enriched_query = self._inject_concepts(plan["reasoning_query"])

        reasoning_state = None
        if plan["needs_reasoning"]:
            reasoning_state = self.think_recursive(enriched_query)

        reply = self.chat_verbalizer.render(user_text, plan, reasoning_state, self.chat)
        self.chat.add("assistant", reply)
        self.chat.remember_reply(reply)

        concept_hits = self.concepts.query(user_text, k=4)

        return {
            "version": "V43",
            "user_text": user_text,
            "topic": self.chat.topic,
            "previous_topic": self.chat.topics.previous(),
            "detour_depth": self.chat.detour_depth,
            "intent": plan["intent"],
            "reply_mode": plan["reply_mode"],
            "verbosity": plan["verbosity"],
            "used_reasoning": reasoning_state is not None,
            "learned_relations": learned,
            "reused_concepts": concept_hits,
            "reply": reply,
            "reasoning": reasoning_state,
            "conversation_turns": len(self.chat.turns),
        }

def main_v43():
    fap = FAPV43()
    print("FAP V43 CHAT -> LEARN -> REUSE -> REASON -> CHAT")
    print("commands: :learn <text> | :json <text> | :concepts | :history | :short | :normal | :long | :quit")

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break

        if q.startswith(":learn "):
            text = q[7:]
            learned = fap._learn_from_user(text)
            print("FAP> learned=" + json.dumps(learned, ensure_ascii=False))
            continue

        if q == ":concepts":
            data = {
                "nodes": len(fap.concepts.nodes),
                "edges": [asdict(x) for x in fap.concepts.edges[-20:]],
            }
            print(json.dumps(data, ensure_ascii=False, indent=2))
            continue

        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue

        if q in (":short", ":normal", ":long"):
            fap.set_verbosity(q[1:])
            print("FAP> verbosity=" + q[1:])
            continue

        if q.startswith(":json "):
            print(json.dumps(fap.chat_once(q[6:]), ensure_ascii=False, indent=2))
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])
        if result["learned_relations"]:
            print("FAP[learned]> " + json.dumps(result["learned_relations"], ensure_ascii=False))


# ============================================================
# FAP V44 - DOMAIN-AGNOSTIC CONCEPT CONSOLIDATION
# ============================================================

V44_GRAPH_FILE = Path(__file__).with_name("fap_v44_graph.json")

def canon_text(s: str) -> str:
    s = normalize(s)
    s = re.sub(r"[「」『』\"'（）()\[\]【】]", "", s)
    s = re.sub(r"[。．.!！?？]+$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def opposite_relation(rel: str) -> str | None:
    pairs = {
        "is": "is_not",
        "is_not": "is",
        "has": "has_not",
        "has_not": "has",
        "can": "cannot",
        "cannot": "can",
        "causes": "does_not_cause",
        "does_not_cause": "causes",
    }
    return pairs.get(rel)

@dataclass
class GenericFact:
    subject: str
    relation: str
    object: str
    confidence: float = 0.6
    support: int = 1
    contradicted: int = 0
    source: str = "user"
    active: bool = True

class UniversalFactExtractor:
    """
    Domain-agnostic Japanese relation extractor.
    It deliberately keeps the relation vocabulary small and generic,
    while preserving unknown predicates instead of discarding them.
    """
    UNCERTAIN = (
        "たぶん","多分","かも","かもしれない","と思う","気がする",
        "仮に","もし","例えば","例として","？","?"
    )

    def extract(self, text: str) -> list[GenericFact]:
        text = text.strip()
        if not text or len(text) > 240:
            return []
        if any(x in text for x in self.UNCERTAIN):
            return []

        # Reject direct requests/commands.
        if any(x in text for x in ("してください","してほしい","お願いします","できますか","でしょうか")):
            return []

        t = re.sub(r"[。．.!！]+$", "", text.strip())

        patterns = [
            (r"^(.{1,50}?)は(.{1,100}?)ではない$", "is_not", 0.72),
            (r"^(.{1,50}?)は(.{1,100}?)である$", "is", 0.74),
            (r"^(.{1,50}?)は(.{1,100}?)です$", "is", 0.72),
            (r"^(.{1,50}?)は(.{1,100}?)だ$", "is", 0.70),

            (r"^(.{1,50}?)は(.{1,100}?)を持つ$", "has", 0.72),
            (r"^(.{1,50}?)には(.{1,100}?)がある$", "has", 0.72),
            (r"^(.{1,50}?)には(.{1,100}?)がない$", "has_not", 0.72),

            (r"^(.{1,50}?)は(.{1,100}?)を使う$", "uses", 0.72),
            (r"^(.{1,50}?)は(.{1,100}?)を含む$", "contains", 0.72),
            (r"^(.{1,50}?)は(.{1,100}?)の一部である$", "part_of", 0.72),
            (r"^(.{1,50}?)は(.{1,100}?)を引き起こす$", "causes", 0.70),
            (r"^(.{1,50}?)は(.{1,100}?)を引き起こさない$", "does_not_cause", 0.70),
            (r"^(.{1,50}?)は(.{1,100}?)できる$", "can", 0.70),
            (r"^(.{1,50}?)は(.{1,100}?)できない$", "cannot", 0.70),
        ]

        for pat, rel, conf in patterns:
            m = re.match(pat, t)
            if m:
                s, o = canon_text(m.group(1)), canon_text(m.group(2))
                if s and o:
                    return [GenericFact(s, rel, o, conf)]

        # Generic fallback: preserve an unknown predicate-like relation.
        # Example: "AはBを最適化する" -> relation="最適化する", object="B"
        m = re.match(r"^(.{1,50}?)は(.{1,80}?)を(.{1,30}?(?:する|させる|生成する|学習する|変換する|比較する))$", t)
        if m:
            s = canon_text(m.group(1))
            o = canon_text(m.group(2))
            rel = canon_text(m.group(3))
            if s and o and rel:
                return [GenericFact(s, rel, o, 0.64)]

        # Conservative copula fallback.
        m = re.match(r"^(.{1,50}?)は(.{1,100}?)$", t)
        if m and len(t) <= 140:
            s, o = canon_text(m.group(1)), canon_text(m.group(2))
            if s and o and not any(x in o for x in ("なぜ","どう","何","いつ","どこ","誰")):
                return [GenericFact(s, "related_to", o, 0.55)]

        return []

class ConsolidatingGraph:
    def __init__(self):
        self.facts: list[GenericFact] = []
        self.aliases: dict[str, str] = {}
        self.load()

    def load(self):
        if not V44_GRAPH_FILE.exists():
            return
        try:
            raw = json.loads(V44_GRAPH_FILE.read_text(encoding="utf-8"))
            self.aliases = dict(raw.get("aliases", {}))
            self.facts = [GenericFact(**x) for x in raw.get("facts", [])]
        except Exception:
            self.facts = []
            self.aliases = {}

    def save(self):
        data = {
            "aliases": self.aliases,
            "facts": [asdict(x) for x in self.facts[-3000:]],
        }
        V44_GRAPH_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def canonical(self, x: str) -> str:
        x = canon_text(x)
        seen = set()
        while x in self.aliases and x not in seen:
            seen.add(x)
            x = self.aliases[x]
        return x

    def add_alias(self, alias: str, canonical: str):
        a, c = canon_text(alias), canon_text(canonical)
        if a and c and a != c:
            self.aliases[a] = c
            self.save()

    def _same(self, a: GenericFact, b: GenericFact) -> bool:
        return (
            self.canonical(a.subject) == self.canonical(b.subject)
            and a.relation == b.relation
            and self.canonical(a.object) == self.canonical(b.object)
        )

    def _contradicts(self, a: GenericFact, b: GenericFact) -> bool:
        if self.canonical(a.subject) != self.canonical(b.subject):
            return False
        if self.canonical(a.object) != self.canonical(b.object):
            return False
        return opposite_relation(a.relation) == b.relation

    def consolidate(self, fact: GenericFact) -> dict:
        fact.subject = self.canonical(fact.subject)
        fact.object = self.canonical(fact.object)

        # Merge duplicates.
        for e in self.facts:
            if self._same(e, fact):
                e.support += 1
                e.confidence = min(0.99, e.confidence + 0.06 * (1.0 - e.confidence))
                e.active = True
                self.save()
                return {"action": "merged", "fact": asdict(e)}

        # Track contradictions rather than deleting either side.
        contradictions = []
        for e in self.facts:
            if self._contradicts(e, fact):
                e.contradicted += 1
                fact.contradicted += 1
                e.confidence = max(0.20, e.confidence - 0.08)
                fact.confidence = max(0.20, fact.confidence - 0.08)
                contradictions.append(asdict(e))

        self.facts.append(fact)
        self.save()

        return {
            "action": "added",
            "fact": asdict(fact),
            "contradictions": contradictions,
        }

    def query(self, text: str, k: int = 8) -> list[dict]:
        hits = []
        for f in self.facts:
            if not f.active:
                continue
            probe = f"{f.subject} {f.relation} {f.object}"
            s = similarity(text, probe)
            if s <= 0.06:
                continue
            score = s * f.confidence * (1.0 + min(0.35, 0.06 * (f.support - 1)))
            hits.append({
                **asdict(f),
                "score": round(score, 4)
            })
        hits.sort(key=lambda x: x["score"], reverse=True)
        return hits[:k]

    def compact(self):
        # Merge exact canonical duplicates that may exist after alias creation.
        merged: list[GenericFact] = []
        for f in self.facts:
            f.subject = self.canonical(f.subject)
            f.object = self.canonical(f.object)

            target = None
            for e in merged:
                if self._same(e, f):
                    target = e
                    break

            if target:
                total_support = target.support + f.support
                target.confidence = min(
                    0.99,
                    (target.confidence * target.support + f.confidence * f.support) / total_support
                )
                target.support = total_support
                target.contradicted += f.contradicted
            else:
                merged.append(f)

        self.facts = merged[-3000:]
        self.save()

class GeneralizationLayer:
    """
    Produces lightweight cross-domain abstractions only when enough support exists.
    It never replaces raw facts.
    """
    def infer_patterns(self, graph: ConsolidatingGraph, min_support: int = 2) -> list[dict]:
        buckets = {}
        for f in graph.facts:
            key = (f.subject, f.relation)
            buckets.setdefault(key, []).append(f)

        patterns = []
        for (subject, relation), fs in buckets.items():
            total_support = sum(f.support for f in fs)
            objs = sorted({f.object for f in fs})
            if total_support >= min_support and len(objs) >= 2:
                patterns.append({
                    "subject": subject,
                    "relation": relation,
                    "objects": objs[:8],
                    "support": total_support,
                    "kind": "multi_object_pattern",
                })
        return patterns

class FAPV44(FAPV42):
    def __init__(self, max_cycles: int = 4, min_improvement: float = 0.025):
        super().__init__(max_cycles=max_cycles, min_improvement=min_improvement)
        self.universal_extractor = UniversalFactExtractor()
        self.graph44 = ConsolidatingGraph()
        self.generalizer = GeneralizationLayer()

    def _learn_general(self, user_text: str) -> list[dict]:
        learned = []
        for fact in self.universal_extractor.extract(user_text):
            res = self.graph44.consolidate(fact)
            learned.append(res)

            # Also expose a compact textual trace to the V40 retrieval organ.
            line = f"{fact.subject} {fact.relation} {fact.object}"
            self.learn(line, weight=fact.confidence, source="v44_graph")
        return learned

    def _graph_context(self, text: str) -> str:
        hits = self.graph44.query(text, k=6)
        if not hits:
            return text

        facts = []
        for h in hits:
            facts.append(
                f'{h["subject"]} {h["relation"]} {h["object"]}'
                f' [conf={h["confidence"]:.2f}, support={h["support"]}]'
            )
        return text + "\n[汎用概念グラフ] " + " / ".join(facts)

    def chat_once(self, user_text: str) -> dict:
        learned = self._learn_general(user_text)

        self.chat.add("user", user_text)
        plan = self.chat_planner.plan(self.chat, user_text)

        enriched = self._graph_context(plan["reasoning_query"])
        reasoning_state = None
        if plan["needs_reasoning"]:
            reasoning_state = self.think_recursive(enriched)

        reply = self.chat_verbalizer.render(user_text, plan, reasoning_state, self.chat)
        self.chat.add("assistant", reply)
        self.chat.remember_reply(reply)

        hits = self.graph44.query(user_text, k=6)
        patterns = self.generalizer.infer_patterns(self.graph44, min_support=2)

        return {
            "version": "V44",
            "user_text": user_text,
            "learned": learned,
            "reused_facts": hits,
            "generalized_patterns": patterns[:10],
            "topic": self.chat.topic,
            "used_reasoning": reasoning_state is not None,
            "reply": reply,
            "reasoning": reasoning_state,
            "conversation_turns": len(self.chat.turns),
        }

def main_v44():
    fap = FAPV44()
    print("FAP V44 GENERAL CONCEPT CONSOLIDATION")
    print("commands: :json <text> | :facts | :compact | :alias A=B | :history | :short | :normal | :long | :quit")

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break

        if q == ":facts":
            print(json.dumps([asdict(x) for x in fap.graph44.facts[-50:]], ensure_ascii=False, indent=2))
            continue

        if q == ":compact":
            fap.graph44.compact()
            print(f"FAP> compacted facts={len(fap.graph44.facts)}")
            continue

        if q.startswith(":alias ") and "=" in q[7:]:
            a, b = q[7:].split("=", 1)
            fap.graph44.add_alias(a, b)
            print(f"FAP> alias {a.strip()} -> {b.strip()}")
            continue

        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue

        if q in (":short", ":normal", ":long"):
            fap.set_verbosity(q[1:])
            print("FAP> verbosity=" + q[1:])
            continue

        if q.startswith(":json "):
            print(json.dumps(fap.chat_once(q[6:]), ensure_ascii=False, indent=2))
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])
        if result["learned"]:
            print("FAP[learned]> " + json.dumps(result["learned"], ensure_ascii=False))


# ============================================================
# FAP V45 - HYPOTHESIS GENERATION / VERIFICATION
# ============================================================

HYP_FILE = Path(__file__).with_name("fap_v45_hypotheses.json")

@dataclass
class Hypothesis:
    subject: str
    relation: str
    object: str
    confidence: float
    basis: list[str]
    status: str = "candidate"   # candidate / supported / conflicted / rejected
    support: int = 0
    conflicts: int = 0

class HypothesisStore:
    def __init__(self):
        self.items: list[Hypothesis] = []
        self.load()

    def load(self):
        if not HYP_FILE.exists():
            return
        try:
            raw = json.loads(HYP_FILE.read_text(encoding="utf-8"))
            self.items = [Hypothesis(**x) for x in raw.get("hypotheses", [])]
        except Exception:
            self.items = []

    def save(self):
        HYP_FILE.write_text(
            json.dumps({"hypotheses":[asdict(x) for x in self.items[-2000:]]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert(self, h: Hypothesis):
        for e in self.items:
            if e.subject == h.subject and e.relation == h.relation and e.object == h.object:
                e.confidence = max(e.confidence, h.confidence)
                e.basis = list(dict.fromkeys(e.basis + h.basis))[:8]
                e.support = max(e.support, h.support)
                e.conflicts = max(e.conflicts, h.conflicts)
                if h.status == "conflicted":
                    e.status = "conflicted"
                elif h.status == "supported" and e.status != "conflicted":
                    e.status = "supported"
                self.save()
                return e
        self.items.append(h)
        self.save()
        return h

class HypothesisEngine:
    TRANSITIVE = {"is", "part_of"}
    WEAK_CHAINS = {
        ("uses","related_to"):"related_to",
        ("contains","part_of"):"related_to",
        ("is","has"):"has",
        ("is","uses"):"uses",
    }

    def _focus_match(self, focus: str, a) -> bool:
        if not focus:
            return True
        f = canon_text(focus)
        probe = canon_text(f"{a.subject} {a.object}")
        # Short labels / abbreviations need lexical inclusion, not only similarity.
        if f and (f in probe or canon_text(a.subject) in f or canon_text(a.object) in f):
            return True
        return similarity(focus, f"{a.subject} {a.object}") >= 0.03

    def generate(self, graph: ConsolidatingGraph, focus: str | None = None, limit: int = 20):
        facts = [f for f in graph.facts if f.active]
        out = []

        for a in facts:
            if focus and not self._focus_match(focus, a):
                continue

            for b in facts:
                if a is b:
                    continue
                if graph.canonical(a.object) != graph.canonical(b.subject):
                    continue

                rel, conf = None, 0.0
                basis = [
                    f"{a.subject} {a.relation} {a.object}",
                    f"{b.subject} {b.relation} {b.object}",
                ]

                if a.relation == b.relation and a.relation in self.TRANSITIVE:
                    rel = a.relation
                    conf = min(a.confidence, b.confidence) * 0.78
                elif (a.relation, b.relation) in self.WEAK_CHAINS:
                    rel = self.WEAK_CHAINS[(a.relation, b.relation)]
                    conf = min(a.confidence, b.confidence) * 0.58

                if rel is None:
                    continue

                s = graph.canonical(a.subject)
                o = graph.canonical(b.object)
                if not s or not o or s == o:
                    continue

                exists = any(
                    graph.canonical(f.subject) == s
                    and f.relation == rel
                    and graph.canonical(f.object) == o
                    for f in facts
                )
                if exists:
                    continue

                out.append(Hypothesis(
                    subject=s,
                    relation=rel,
                    object=o,
                    confidence=round(max(0.05, min(0.95, conf)), 3),
                    basis=basis,
                ))
                if len(out) >= limit:
                    return out
        return out

    def verify(self, h: Hypothesis, graph: ConsolidatingGraph) -> Hypothesis:
        positive, negative = 0, 0

        for f in graph.facts:
            same_s = graph.canonical(f.subject) == graph.canonical(h.subject)
            same_o = graph.canonical(f.object) == graph.canonical(h.object)
            if not (same_s and same_o):
                continue
            if f.relation == h.relation:
                positive += f.support
            if opposite_relation(h.relation) == f.relation:
                negative += f.support

        h.support = positive
        h.conflicts = negative

        if negative > 0 and negative >= positive:
            h.status = "conflicted"
            h.confidence = max(0.05, h.confidence - 0.20)
        elif positive > 0:
            h.status = "supported"
            h.confidence = min(0.98, h.confidence + 0.15)
        else:
            h.status = "candidate"

        return h

class HypothesisReasoner:
    def __init__(self):
        self.engine = HypothesisEngine()
        self.store = HypothesisStore()

    def run(self, graph: ConsolidatingGraph, focus: str | None = None) -> list[dict]:
        candidates = self.engine.generate(graph, focus=focus, limit=24)
        results = []
        for h in candidates:
            h = self.engine.verify(h, graph)
            saved = self.store.upsert(h)
            results.append(asdict(saved))
        results.sort(
            key=lambda x: (
                x["status"] == "supported",
                x["status"] != "conflicted",
                x["confidence"],
                x["support"],
            ),
            reverse=True,
        )
        return results[:12]

class FAPV45(FAPV44):
    def __init__(self, max_cycles: int = 4, min_improvement: float = 0.025):
        super().__init__(max_cycles=max_cycles, min_improvement=min_improvement)
        self.hyp_reasoner = HypothesisReasoner()

    def _hypothesis_context(self, user_text: str):
        hyps = self.hyp_reasoner.run(self.graph44, focus=user_text)
        if not hyps:
            return user_text, []
        lines = [
            f'{h["subject"]} {h["relation"]} {h["object"]}'
            f' [status={h["status"]}, conf={h["confidence"]:.2f}]'
            for h in hyps[:6]
        ]
        return user_text + "\n[生成仮説] " + " / ".join(lines), hyps

    def chat_once(self, user_text: str) -> dict:
        learned = self._learn_general(user_text)
        self.chat.add("user", user_text)
        plan = self.chat_planner.plan(self.chat, user_text)

        graph_enriched = self._graph_context(plan["reasoning_query"])
        hyp_enriched, hyps = self._hypothesis_context(graph_enriched)

        reasoning_state = None
        if plan["needs_reasoning"]:
            reasoning_state = self.think_recursive(hyp_enriched)

        reply = self.chat_verbalizer.render(user_text, plan, reasoning_state, self.chat)
        self.chat.add("assistant", reply)
        self.chat.remember_reply(reply)

        return {
            "version":"V45",
            "user_text":user_text,
            "learned":learned,
            "hypotheses":hyps,
            "topic":self.chat.topic,
            "used_reasoning":reasoning_state is not None,
            "reply":reply,
            "reasoning":reasoning_state,
            "conversation_turns":len(self.chat.turns),
        }

def main_v45():
    fap = FAPV45()
    print("FAP V45 HYPOTHESIS ENGINE")
    print("commands: :json <text> | :facts | :hyp | :compact | :alias A=B | :history | :quit")

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q",":quit","exit","quit"):
            break

        if q == ":facts":
            print(json.dumps([asdict(x) for x in fap.graph44.facts[-50:]],
                             ensure_ascii=False, indent=2))
            continue

        if q == ":hyp":
            print(json.dumps([asdict(x) for x in fap.hyp_reasoner.store.items[-50:]],
                             ensure_ascii=False, indent=2))
            continue

        if q == ":compact":
            fap.graph44.compact()
            print(f"FAP> compacted facts={len(fap.graph44.facts)}")
            continue

        if q.startswith(":alias ") and "=" in q[7:]:
            a,b = q[7:].split("=",1)
            fap.graph44.add_alias(a,b)
            print(f"FAP> alias {a.strip()} -> {b.strip()}")
            continue

        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue

        if q.startswith(":json "):
            print(json.dumps(fap.chat_once(q[6:]), ensure_ascii=False, indent=2))
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])
        if result["hypotheses"]:
            print("FAP[hyp]> " + json.dumps(result["hypotheses"][:5], ensure_ascii=False))


import hashlib

# ============================================================
# FAP V46 - GENERATIONAL SEMANTIC GARBAGE COLLECTION
# ============================================================

GC_META_FILE = Path(__file__).with_name("fap_v46_gc.json")

@dataclass
class GCMetrics:
    turns: int
    memory: int
    facts: int
    hypotheses: int
    semantic_units: int
    capacity: int
    occupancy: float
    level: str

class SemanticGarbageCollector:
    """
    Three-stage semantic GC.

    Occupancy thresholds:
      < 70%   : no GC
      70-85%  : light   -> dedupe / compact only
      85-95%  : hard    -> plus low-value pruning
      >=95%   : emergency -> aggressively return toward 70%

    Important rule:
    raw contradictions are not silently erased merely because they conflict.
    Well-supported facts and supported hypotheses receive strong protection.
    """

    def __init__(
        self,
        capacity: int = 512,
        light_at: float = 0.70,
        hard_at: float = 0.85,
        emergency_at: float = 0.95,
        periodic_turns: int = 32,
    ):
        self.capacity = max(64, int(capacity))
        self.light_at = float(light_at)
        self.hard_at = float(hard_at)
        self.emergency_at = float(emergency_at)
        self.periodic_turns = max(8, int(periodic_turns))
        self.turn_counter = 0
        self.collections = 0
        self.last_report = {}
        self.load_meta()

    def load_meta(self):
        if not GC_META_FILE.exists():
            return
        try:
            d = json.loads(GC_META_FILE.read_text(encoding="utf-8"))
            self.turn_counter = int(d.get("turn_counter", 0))
            self.collections = int(d.get("collections", 0))
            self.last_report = dict(d.get("last_report", {}))
        except Exception:
            pass

    def save_meta(self):
        GC_META_FILE.write_text(
            json.dumps({
                "turn_counter": self.turn_counter,
                "collections": self.collections,
                "last_report": self.last_report,
                "capacity": self.capacity,
                "thresholds": {
                    "light": self.light_at,
                    "hard": self.hard_at,
                    "emergency": self.emergency_at,
                },
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    @staticmethod
    def _sig(text: str) -> str:
        return hashlib.sha1(canon_text(text).encode("utf-8")).hexdigest()[:16]

    def metrics(self, fap) -> GCMetrics:
        # Conversation is short-term and already bounded separately.
        turns = len(getattr(fap.chat, "turns", []))
        memory = len(getattr(fap, "memory", []))
        facts = len(getattr(fap.graph44, "facts", []))
        hypotheses = len(getattr(fap.hyp_reasoner.store, "items", []))

        # Treat two chat turns as roughly one persistent semantic unit,
        # because short-term chat is disposable and capped.
        semantic_units = memory + facts + hypotheses + (turns // 2)
        occupancy = semantic_units / self.capacity

        if occupancy >= self.emergency_at:
            level = "emergency"
        elif occupancy >= self.hard_at:
            level = "hard"
        elif occupancy >= self.light_at:
            level = "light"
        else:
            level = "none"

        return GCMetrics(
            turns=turns,
            memory=memory,
            facts=facts,
            hypotheses=hypotheses,
            semantic_units=semantic_units,
            capacity=self.capacity,
            occupancy=round(occupancy, 4),
            level=level,
        )

    def _dedupe_memory(self, fap):
        # Keep the strongest representative of semantically identical text.
        best = {}
        order = []
        for m in fap.memory:
            key = self._sig(m.text)
            if key not in best:
                best[key] = m
                order.append(key)
            else:
                if m.weight > best[key].weight:
                    best[key] = m
        fap.memory = [best[k] for k in order][-1000:]

    def _dedupe_hypotheses(self, fap):
        merged = {}
        order = []
        for h in fap.hyp_reasoner.store.items:
            key = (
                canon_text(h.subject),
                h.relation,
                canon_text(h.object),
            )
            if key not in merged:
                merged[key] = h
                order.append(key)
            else:
                e = merged[key]
                e.confidence = max(e.confidence, h.confidence)
                e.support = max(e.support, h.support)
                e.conflicts = max(e.conflicts, h.conflicts)
                e.basis = list(dict.fromkeys(e.basis + h.basis))[:8]
                if h.status == "supported":
                    e.status = "supported"
                elif h.status == "conflicted" and e.status != "supported":
                    e.status = "conflicted"
        fap.hyp_reasoner.store.items = [merged[k] for k in order][-2000:]

    @staticmethod
    def _memory_value(m) -> float:
        source_bonus = 0.20 if m.source in ("concept", "v44_graph") else 0.0
        return float(m.weight) + source_bonus

    @staticmethod
    def _fact_value(f) -> float:
        # Contradictions are not auto-deleted; support protects both sides.
        contradiction_bonus = min(0.20, 0.04 * f.contradicted)
        support_bonus = min(0.35, 0.06 * max(0, f.support - 1))
        return float(f.confidence) + support_bonus + contradiction_bonus

    @staticmethod
    def _hyp_value(h) -> float:
        status_bonus = {
            "supported": 0.45,
            "candidate": 0.05,
            "conflicted": 0.00,
            "rejected": -0.25,
        }.get(h.status, 0.0)
        support_bonus = min(0.25, 0.05 * h.support)
        conflict_penalty = min(0.25, 0.05 * h.conflicts)
        return float(h.confidence) + status_bonus + support_bonus - conflict_penalty

    def _prune_to_target(self, fap, target_units: int, aggressive: bool):
        """
        Remove lowest-value persistent items while protecting strong knowledge.
        Facts are pruned last.
        """
        def current():
            return self.metrics(fap).semantic_units

        # 1) Hypotheses first: candidates/rejected/conflicted low-value.
        if current() > target_units:
            hs = list(fap.hyp_reasoner.store.items)
            hs.sort(key=self._hyp_value)
            protected = []
            removable = []
            for h in hs:
                value = self._hyp_value(h)
                if h.status == "supported" and value >= 0.85:
                    protected.append(h)
                else:
                    removable.append(h)
            keep = list(protected)
            # Keep highest-value remainder that fits budget pressure.
            for h in reversed(removable):
                if current() <= target_units:
                    keep.append(h)
                else:
                    # virtual removal by not keeping
                    pass
            # The loop above cannot observe current() until assignment; compute count directly.
            need_remove = max(0, self.metrics(fap).semantic_units - target_units)
            removable_sorted = sorted(removable, key=self._hyp_value)
            remove_set = set(id(x) for x in removable_sorted[:need_remove])
            fap.hyp_reasoner.store.items = [
                h for h in hs if id(h) not in remove_set
            ]

        # 2) Ordinary memory.
        if current() > target_units:
            mem = list(fap.memory)
            need_remove = current() - target_units
            ranked = sorted(mem, key=self._memory_value)
            protected_ids = {
                id(m) for m in mem
                if self._memory_value(m) >= (0.92 if not aggressive else 1.05)
            }
            removed = 0
            out = []
            remove_ids = set()
            for m in ranked:
                if removed >= need_remove:
                    break
                if id(m) in protected_ids:
                    continue
                remove_ids.add(id(m))
                removed += 1
            out = [m for m in mem if id(m) not in remove_ids]
            fap.memory = out

        # 3) Facts only in emergency/very hard pressure, and preserve high support.
        if aggressive and current() > target_units:
            facts = list(fap.graph44.facts)
            need_remove = current() - target_units
            ranked = sorted(facts, key=self._fact_value)
            remove_ids = set()
            removed = 0
            for f in ranked:
                if removed >= need_remove:
                    break
                # Never remove well-supported or contradiction-bearing facts here.
                if f.support >= 2 or f.contradicted > 0 or self._fact_value(f) >= 0.80:
                    continue
                remove_ids.add(id(f))
                removed += 1
            fap.graph44.facts = [f for f in facts if id(f) not in remove_ids]

    def collect(self, fap, force_level: str | None = None):
        before = self.metrics(fap)
        level = force_level or before.level

        if level == "none":
            report = {
                "performed": False,
                "level": "none",
                "before": asdict(before),
                "after": asdict(before),
                "reason": "below threshold",
            }
            self.last_report = report
            self.save_meta()
            return report

        # Always compact before deletion.
        self._dedupe_memory(fap)
        fap.graph44.compact()
        self._dedupe_hypotheses(fap)

        after_compact = self.metrics(fap)

        if level == "light":
            target = int(self.capacity * 0.68)
            if after_compact.semantic_units > target:
                self._prune_to_target(fap, target, aggressive=False)

        elif level == "hard":
            target = int(self.capacity * 0.72)
            self._prune_to_target(fap, target, aggressive=False)

        elif level == "emergency":
            target = int(self.capacity * 0.70)
            self._prune_to_target(fap, target, aggressive=True)

        # Keep short-term conversation separately bounded.
        if len(fap.chat.turns) > min(fap.chat.max_turns, 40):
            fap.chat.turns = fap.chat.turns[-min(fap.chat.max_turns, 40):]

        fap.save_memory()
        fap.graph44.save()
        fap.hyp_reasoner.store.save()

        after = self.metrics(fap)
        self.collections += 1
        report = {
            "performed": True,
            "level": level,
            "before": asdict(before),
            "after_compact": asdict(after_compact),
            "after": asdict(after),
            "freed_units": max(0, before.semantic_units - after.semantic_units),
        }
        self.last_report = report
        self.save_meta()
        return report

    def on_turn(self, fap):
        self.turn_counter += 1
        m = self.metrics(fap)

        # Threshold GC takes precedence.
        if m.level != "none":
            return self.collect(fap)

        # Periodic light maintenance, but compaction only below threshold.
        if self.turn_counter % self.periodic_turns == 0:
            return self.collect(fap, force_level="light")

        self.save_meta()
        return {
            "performed": False,
            "level": "none",
            "before": asdict(m),
            "after": asdict(m),
            "reason": "not_due",
        }

class FAPV46(FAPV45):
    def __init__(
        self,
        max_cycles: int = 4,
        min_improvement: float = 0.025,
        gc_capacity: int = 512,
    ):
        super().__init__(max_cycles=max_cycles, min_improvement=min_improvement)
        self.gc = SemanticGarbageCollector(capacity=gc_capacity)

    def chat_once(self, user_text: str) -> dict:
        # Preserve V45 behavior.
        result = super().chat_once(user_text)

        # Then perform bounded post-turn maintenance.
        gc_report = self.gc.on_turn(self)
        result["version"] = "V46"
        result["gc"] = gc_report
        result["memory_metrics"] = asdict(self.gc.metrics(self))
        return result

def main_v46():
    fap = FAPV46()
    print("FAP V46 GENERATIONAL GC")
    print("commands: :json <text> | :gc | :gcstat | :facts | :hyp | :history | :quit")

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break

        if q == ":gc":
            print(json.dumps(fap.gc.collect(fap, force_level="hard"), ensure_ascii=False, indent=2))
            continue

        if q == ":gcstat":
            print(json.dumps(asdict(fap.gc.metrics(fap)), ensure_ascii=False, indent=2))
            continue

        if q == ":facts":
            print(json.dumps([asdict(x) for x in fap.graph44.facts[-50:]], ensure_ascii=False, indent=2))
            continue

        if q == ":hyp":
            print(json.dumps([asdict(x) for x in fap.hyp_reasoner.store.items[-50:]], ensure_ascii=False, indent=2))
            continue

        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue

        if q.startswith(":json "):
            print(json.dumps(fap.chat_once(q[6:]), ensure_ascii=False, indent=2))
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])
        gc = result["gc"]
        if gc.get("performed"):
            print(
                f'FAP[gc]> {gc["level"]}: '
                f'{gc["before"]["semantic_units"]} -> {gc["after"]["semantic_units"]} units'
            )

# ============================================================
# FAP V47 - HYPOTHESIS COMPETITION / VERIFICATION PRIORITY
# ============================================================

COMPETE_FILE = Path(__file__).with_name("fap_v47_competition.json")

@dataclass
class HypothesisScore:
    subject: str
    relation: str
    object: str
    status: str
    base_confidence: float
    support: int
    conflicts: int
    novelty: float
    verification_cost: float
    priority: float
    reason: str

class HypothesisCompetition:
    def __init__(self):
        self.history = []
        self.load()

    def load(self):
        if not COMPETE_FILE.exists():
            return
        try:
            raw = json.loads(COMPETE_FILE.read_text(encoding="utf-8"))
            self.history = list(raw.get("history", []))[-500:]
        except Exception:
            self.history = []

    def save(self):
        COMPETE_FILE.write_text(
            json.dumps({"history": self.history[-500:]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _verification_cost(h: Hypothesis) -> float:
        cost = 0.25 + 0.08 * len(h.basis) + 0.10 * h.conflicts
        if h.status == "conflicted":
            cost += 0.10
        return round(min(1.0, cost), 3)

    @staticmethod
    def _novelty(h: Hypothesis, graph: ConsolidatingGraph) -> float:
        best = 0.0
        probe = f"{h.subject} {h.relation} {h.object}"
        for f in graph.facts:
            best = max(best, similarity(probe, f"{f.subject} {f.relation} {f.object}"))
        return round(max(0.0, 1.0 - best), 3)

    def score(self, h: Hypothesis, graph: ConsolidatingGraph) -> HypothesisScore:
        novelty = self._novelty(h, graph)
        cost = self._verification_cost(h)

        confidence_term = 0.40 * float(h.confidence)
        support_term = min(0.20, 0.05 * h.support)
        conflict_term = min(0.42, 0.16 * h.conflicts)
        novelty_term = 0.18 * novelty
        cost_penalty = 0.16 * cost

        # Settled hypotheses should stop consuming verification budget.
        settled_penalty = 0.0
        if h.status == "supported" and h.support >= 3 and h.conflicts == 0:
            settled_penalty = 0.38

        # Unresolved contradictions are explicitly information-rich.
        unresolved_bonus = 0.12 if h.status == "conflicted" and h.conflicts > 0 else 0.0

        priority = (
            confidence_term + support_term + conflict_term + novelty_term
            + unresolved_bonus - cost_penalty - settled_penalty
        )
        priority = round(max(0.0, min(1.0, priority)), 4)

        if h.conflicts > 0:
            reason = "矛盾解消の情報価値が高い"
        elif settled_penalty:
            reason = "既に十分支持され再検証の価値が低い"
        elif novelty >= 0.65:
            reason = "新規性が高い"
        elif h.status == "candidate":
            reason = "未検証候補"
        else:
            reason = "支持・新規性・コストのバランス"

        return HypothesisScore(
            subject=h.subject,
            relation=h.relation,
            object=h.object,
            status=h.status,
            base_confidence=round(float(h.confidence), 3),
            support=int(h.support),
            conflicts=int(h.conflicts),
            novelty=novelty,
            verification_cost=cost,
            priority=priority,
            reason=reason,
        )

    def compete(self, hypotheses: list[Hypothesis], graph: ConsolidatingGraph, top_k: int = 8):
        scored = [self.score(h, graph) for h in hypotheses]
        scored.sort(
            key=lambda x: (x.priority, x.conflicts, x.novelty, x.base_confidence),
            reverse=True,
        )
        return scored[:top_k]

    def record(self, ranked):
        if ranked:
            self.history.append({"ranking": [asdict(x) for x in ranked]})
            self.save()

class VerificationScheduler:
    def __init__(self, budget: int = 3):
        self.budget = max(1, int(budget))

    def select(self, ranked):
        return ranked[:self.budget]

class FAPV47(FAPV46):
    def __init__(self, max_cycles=4, min_improvement=0.025, gc_capacity=512, verification_budget=3):
        super().__init__(
            max_cycles=max_cycles,
            min_improvement=min_improvement,
            gc_capacity=gc_capacity,
        )
        self.competition = HypothesisCompetition()
        self.verification_scheduler = VerificationScheduler(verification_budget)

    def _compete_hypotheses(self, user_text: str):
        generated = self.hyp_reasoner.engine.generate(
            self.graph44,
            focus=user_text,
            limit=24,
        )
        verified = [
            self.hyp_reasoner.engine.verify(h, self.graph44)
            for h in generated
        ]
        ranked = self.competition.compete(verified, self.graph44, top_k=8)
        selected = self.verification_scheduler.select(ranked)
        self.competition.record(ranked)
        return verified, ranked, selected

    def _competition_context(self, text: str, ranked) -> str:
        if not ranked:
            return text
        lines = [
            f"{r.subject} {r.relation} {r.object} "
            f"[priority={r.priority:.2f}, reason={r.reason}]"
            for r in ranked[:5]
        ]
        return text + "\n[仮説競争] " + " / ".join(lines)

    def chat_once(self, user_text: str) -> dict:
        learned = self._learn_general(user_text)

        self.chat.add("user", user_text)
        plan = self.chat_planner.plan(self.chat, user_text)

        graph_enriched = self._graph_context(plan["reasoning_query"])
        _, ranked, selected = self._compete_hypotheses(graph_enriched)
        compete_enriched = self._competition_context(graph_enriched, ranked)

        reasoning_state = None
        if plan["needs_reasoning"]:
            reasoning_state = self.think_recursive(compete_enriched)

        reply = self.chat_verbalizer.render(user_text, plan, reasoning_state, self.chat)
        self.chat.add("assistant", reply)
        self.chat.remember_reply(reply)

        gc_report = self.gc.on_turn(self)

        return {
            "version": "V47",
            "user_text": user_text,
            "learned": learned,
            "competition": [asdict(x) for x in ranked],
            "selected_for_verification": [asdict(x) for x in selected],
            "topic": self.chat.topic,
            "used_reasoning": reasoning_state is not None,
            "reply": reply,
            "reasoning": reasoning_state,
            "conversation_turns": len(self.chat.turns),
            "gc": gc_report,
            "memory_metrics": asdict(self.gc.metrics(self)),
        }

def main_v47():
    fap = FAPV47()
    print("FAP V47 HYPOTHESIS COMPETITION")
    print("commands: :json <text> | :rank | :gc | :gcstat | :facts | :hyp | :history | :quit")
    last = None

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break

        if q == ":rank":
            print(json.dumps(last.get("competition", []) if last else [],
                             ensure_ascii=False, indent=2))
            continue
        if q == ":gc":
            print(json.dumps(fap.gc.collect(fap, force_level="hard"),
                             ensure_ascii=False, indent=2))
            continue
        if q == ":gcstat":
            print(json.dumps(asdict(fap.gc.metrics(fap)),
                             ensure_ascii=False, indent=2))
            continue
        if q == ":facts":
            print(json.dumps([asdict(x) for x in fap.graph44.facts[-50:]],
                             ensure_ascii=False, indent=2))
            continue
        if q == ":hyp":
            print(json.dumps([asdict(x) for x in fap.hyp_reasoner.store.items[-50:]],
                             ensure_ascii=False, indent=2))
            continue
        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue
        if q.startswith(":json "):
            last = fap.chat_once(q[6:])
            print(json.dumps(last, ensure_ascii=False, indent=2))
            continue

        last = fap.chat_once(q)
        print("FAP> " + last["reply"])
        if last["selected_for_verification"]:
            print("FAP[verify-next]> " + json.dumps(
                last["selected_for_verification"],
                ensure_ascii=False
            ))


# ============================================================
# FAP V48 - PARALLEL HYPOTHESIS SEARCH
# ============================================================

PARALLEL_FILE = Path(__file__).with_name("fap_v48_parallel.json")

@dataclass
class BranchState:
    branch_id: int
    subject: str
    relation: str
    object: str
    priority: float
    budget: int
    cycles: int = 0
    score: float = 0.0
    support: int = 0
    conflicts: int = 0
    confidence: float = 0.0
    status: str = "candidate"
    alive: bool = True
    trace: list[str] = None

    def __post_init__(self):
        if self.trace is None:
            self.trace = []

class ParallelHypothesisExplorer:
    def __init__(self, total_budget: int = 12, max_branches: int = 4):
        self.total_budget = max(2, int(total_budget))
        self.max_branches = max(1, int(max_branches))
        self.history = []
        self.load()

    def load(self):
        if not PARALLEL_FILE.exists():
            return
        try:
            raw = json.loads(PARALLEL_FILE.read_text(encoding="utf-8"))
            self.history = list(raw.get("history", []))[-300:]
        except Exception:
            self.history = []

    def save(self):
        PARALLEL_FILE.write_text(
            json.dumps({"history": self.history[-300:]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _initial_budget(self, ranked):
        ranked = ranked[:self.max_branches]
        if not ranked:
            return []
        weights = [max(0.05, float(r.priority)) for r in ranked]
        total = sum(weights)
        raw = [max(1, int(round(self.total_budget * w / total))) for w in weights]

        while sum(raw) > self.total_budget:
            i = max(range(len(raw)), key=lambda j: raw[j])
            if raw[i] > 1:
                raw[i] -= 1
            else:
                break
        while sum(raw) < self.total_budget:
            i = max(range(len(raw)), key=lambda j: weights[j])
            raw[i] += 1
        return raw

    def build_branches(self, ranked):
        ranked = ranked[:self.max_branches]
        budgets = self._initial_budget(ranked)
        return [
            BranchState(
                branch_id=i,
                subject=r.subject,
                relation=r.relation,
                object=r.object,
                priority=r.priority,
                budget=b,
                conflicts=r.conflicts,
                confidence=r.base_confidence,
                status=r.status,
                score=r.priority,
            )
            for i, (r, b) in enumerate(zip(ranked, budgets), start=1)
        ]

    @staticmethod
    def _branch_query(b: BranchState) -> str:
        return (
            f"仮説: {b.subject} {b.relation} {b.object}\n"
            "この仮説の支持・矛盾・反例を優先して検証する。"
        )

    def _step(self, fap, b: BranchState):
        st = fap.think_recursive(self._branch_query(b))
        b.cycles += 1

        frame = st.get("frame", {})
        conflicts = frame.get("conflicts", [])
        evidence = frame.get("evidence", [])
        conf = float(st.get("confidence", 0.0))

        b.support += len(evidence)
        b.conflicts += len(conflicts)
        b.confidence = max(b.confidence, conf)

        evidence_term = min(0.30, 0.06 * b.support)
        conflict_penalty = min(0.35, 0.08 * b.conflicts)
        improvement_term = 0.10 if conf > b.score else 0.0

        b.score = round(max(
            0.0,
            min(
                1.0,
                0.50 * b.priority
                + 0.35 * b.confidence
                + evidence_term
                + improvement_term
                - conflict_penalty
            )
        ), 4)

        b.trace.append(
            f"cycle={b.cycles}, conf={conf:.3f}, evidence={len(evidence)}, "
            f"conflicts={len(conflicts)}, score={b.score:.3f}"
        )

        if b.cycles >= 2 and b.score < 0.16:
            b.alive = False
            b.trace.append("pruned=low_score")

    def _reallocate(self, branches):
        alive = [b for b in branches if b.alive]
        if not alive:
            return

        best = max(alive, key=lambda b: b.score)
        donors = sorted(
            [b for b in alive if b.branch_id != best.branch_id and b.budget > b.cycles + 1],
            key=lambda b: b.score
        )

        for d in donors:
            if best.score - d.score >= 0.12:
                d.budget -= 1
                best.budget += 1
                d.trace.append(f"budget-1 -> branch{best.branch_id}")
                best.trace.append(f"budget+1 <- branch{d.branch_id}")
                break

    def run(self, fap, ranked):
        branches = self.build_branches(ranked)
        if not branches:
            return {"branches": [], "winner": None, "used_budget": 0, "total_budget": self.total_budget}

        used = 0
        while used < self.total_budget:
            runnable = [b for b in branches if b.alive and b.cycles < b.budget]
            if not runnable:
                break

            runnable.sort(key=lambda b: (b.cycles == 0, b.score), reverse=True)
            b = runnable[0]
            self._step(fap, b)
            used += 1

            if used % max(2, len(branches)) == 0:
                self._reallocate(branches)

        alive = [b for b in branches if b.alive]
        winner = max(alive or branches, key=lambda b: b.score)

        result = {
            "branches": [asdict(b) for b in branches],
            "winner": asdict(winner),
            "used_budget": used,
            "total_budget": self.total_budget,
        }
        self.history.append(result)
        self.save()
        return result

class FAPV48(FAPV47):
    def __init__(
        self,
        max_cycles=4,
        min_improvement=0.025,
        gc_capacity=512,
        verification_budget=3,
        parallel_budget=12,
        max_parallel_branches=4,
    ):
        super().__init__(
            max_cycles=max_cycles,
            min_improvement=min_improvement,
            gc_capacity=gc_capacity,
            verification_budget=verification_budget,
        )
        self.parallel = ParallelHypothesisExplorer(
            total_budget=parallel_budget,
            max_branches=max_parallel_branches,
        )

    def chat_once(self, user_text: str) -> dict:
        learned = self._learn_general(user_text)

        self.chat.add("user", user_text)
        plan = self.chat_planner.plan(self.chat, user_text)

        graph_enriched = self._graph_context(plan["reasoning_query"])
        _, ranked, selected = self._compete_hypotheses(graph_enriched)

        parallel_result = self.parallel.run(self, selected)

        enriched = graph_enriched
        if parallel_result["winner"]:
            w = parallel_result["winner"]
            enriched += (
                "\n[並列探索トップ候補] "
                f'{w["subject"]} {w["relation"]} {w["object"]}'
                f' [score={w["score"]:.2f}, cycles={w["cycles"]}]'
            )

        reasoning_state = None
        if plan["needs_reasoning"]:
            reasoning_state = self.think_recursive(enriched)

        reply = self.chat_verbalizer.render(
            user_text, plan, reasoning_state, self.chat
        )
        self.chat.add("assistant", reply)
        self.chat.remember_reply(reply)

        gc_report = self.gc.on_turn(self)

        return {
            "version": "V48",
            "user_text": user_text,
            "learned": learned,
            "competition": [asdict(x) for x in ranked],
            "selected_for_parallel": [asdict(x) for x in selected],
            "parallel_search": parallel_result,
            "topic": self.chat.topic,
            "used_reasoning": reasoning_state is not None,
            "reply": reply,
            "reasoning": reasoning_state,
            "conversation_turns": len(self.chat.turns),
            "gc": gc_report,
            "memory_metrics": asdict(self.gc.metrics(self)),
        }

def main_v48():
    fap = FAPV48()
    print("FAP V48 PARALLEL HYPOTHESIS SEARCH")
    print("commands: :json <text> | :parallel | :rank | :gc | :gcstat | :facts | :hyp | :history | :quit")
    last = None

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break

        if q == ":parallel":
            print(json.dumps(last.get("parallel_search", {}) if last else {}, ensure_ascii=False, indent=2))
            continue
        if q == ":rank":
            print(json.dumps(last.get("competition", []) if last else [], ensure_ascii=False, indent=2))
            continue
        if q == ":gc":
            print(json.dumps(fap.gc.collect(fap, force_level="hard"), ensure_ascii=False, indent=2))
            continue
        if q == ":gcstat":
            print(json.dumps(asdict(fap.gc.metrics(fap)), ensure_ascii=False, indent=2))
            continue
        if q == ":facts":
            print(json.dumps([asdict(x) for x in fap.graph44.facts[-50:]], ensure_ascii=False, indent=2))
            continue
        if q == ":hyp":
            print(json.dumps([asdict(x) for x in fap.hyp_reasoner.store.items[-50:]], ensure_ascii=False, indent=2))
            continue
        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue
        if q.startswith(":json "):
            last = fap.chat_once(q[6:])
            print(json.dumps(last, ensure_ascii=False, indent=2))
            continue

        last = fap.chat_once(q)
        print("FAP> " + last["reply"])
        w = last["parallel_search"].get("winner")
        if w:
            print(
                "FAP[parallel-top]> "
                f'{w["subject"]} {w["relation"]} {w["object"]} '
                f'score={w["score"]:.3f}, cycles={w["cycles"]}'
            )


# ============================================================
# FAP V49 - TIMEOUT / DEADLINE GUARD
# ============================================================

import time

@dataclass
class TimeoutPolicy:
    branch_seconds: float = 0.75
    parallel_seconds: float = 2.50
    turn_seconds: float = 4.00

class Deadline:
    def __init__(self, seconds: float):
        self.seconds = max(0.001, float(seconds))
        self.started = time.perf_counter()

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    @property
    def remaining(self) -> float:
        return max(0.0, self.seconds - self.elapsed)

    @property
    def expired(self) -> bool:
        return self.elapsed >= self.seconds

class TimedParallelHypothesisExplorer(ParallelHypothesisExplorer):
    def __init__(
        self,
        total_budget: int = 12,
        max_branches: int = 4,
        branch_seconds: float = 0.75,
        parallel_seconds: float = 2.50,
    ):
        super().__init__(total_budget=total_budget, max_branches=max_branches)
        self.branch_seconds = max(0.01, float(branch_seconds))
        self.parallel_seconds = max(0.05, float(parallel_seconds))

    def _timed_step(self, fap, b: BranchState, parallel_deadline: Deadline):
        if parallel_deadline.expired:
            return "parallel_timeout"

        branch_deadline = Deadline(min(self.branch_seconds, parallel_deadline.remaining))
        started = time.perf_counter()

        # Current organs are synchronous and lightweight, so we check deadline
        # immediately before and after one atomic reasoning step.
        if branch_deadline.expired:
            b.alive = False
            b.trace.append("timeout=before_step")
            return "branch_timeout"

        self._step(fap, b)
        elapsed = time.perf_counter() - started

        if elapsed >= self.branch_seconds:
            b.alive = False
            b.trace.append(f"timeout=branch elapsed={elapsed:.4f}s")
            return "branch_timeout"

        if parallel_deadline.expired:
            b.trace.append("timeout=parallel_after_step")
            return "parallel_timeout"

        return "ok"

    def run(self, fap, ranked):
        branches = self.build_branches(ranked)
        if not branches:
            return {
                "branches": [],
                "winner": None,
                "used_budget": 0,
                "total_budget": self.total_budget,
                "stop_reason": "no_hypotheses",
                "elapsed_seconds": 0.0,
            }

        deadline = Deadline(self.parallel_seconds)
        used = 0
        stop_reason = "completed"

        while used < self.total_budget:
            if deadline.expired:
                stop_reason = "parallel_timeout"
                break

            runnable = [b for b in branches if b.alive and b.cycles < b.budget]
            if not runnable:
                stop_reason = "branches_exhausted"
                break

            runnable.sort(key=lambda b: (b.cycles == 0, b.score), reverse=True)
            b = runnable[0]

            outcome = self._timed_step(fap, b, deadline)
            if outcome in ("ok", "branch_timeout", "parallel_timeout"):
                used += 1

            if outcome == "parallel_timeout":
                stop_reason = "parallel_timeout"
                break

            if used % max(2, len(branches)) == 0:
                self._reallocate(branches)

        if used >= self.total_budget and stop_reason == "completed":
            stop_reason = "budget_exhausted"

        alive = [b for b in branches if b.alive]
        winner = max(alive or branches, key=lambda b: b.score)

        result = {
            "branches": [asdict(b) for b in branches],
            "winner": asdict(winner),
            "used_budget": used,
            "total_budget": self.total_budget,
            "stop_reason": stop_reason,
            "elapsed_seconds": round(deadline.elapsed, 4),
            "parallel_timeout_seconds": self.parallel_seconds,
            "branch_timeout_seconds": self.branch_seconds,
        }
        self.history.append(result)
        self.save()
        return result

class FAPV49(FAPV48):
    def __init__(
        self,
        max_cycles=4,
        min_improvement=0.025,
        gc_capacity=512,
        verification_budget=3,
        parallel_budget=12,
        max_parallel_branches=4,
        branch_timeout=0.75,
        parallel_timeout=2.50,
        turn_timeout=4.00,
    ):
        super().__init__(
            max_cycles=max_cycles,
            min_improvement=min_improvement,
            gc_capacity=gc_capacity,
            verification_budget=verification_budget,
            parallel_budget=parallel_budget,
            max_parallel_branches=max_parallel_branches,
        )

        self.timeout_policy = TimeoutPolicy(
            branch_seconds=branch_timeout,
            parallel_seconds=parallel_timeout,
            turn_seconds=turn_timeout,
        )

        self.parallel = TimedParallelHypothesisExplorer(
            total_budget=parallel_budget,
            max_branches=max_parallel_branches,
            branch_seconds=branch_timeout,
            parallel_seconds=parallel_timeout,
        )

    def chat_once(self, user_text: str) -> dict:
        turn_deadline = Deadline(self.timeout_policy.turn_seconds)
        stages = []

        learned = self._learn_general(user_text)
        stages.append("learn")

        self.chat.add("user", user_text)
        plan = self.chat_planner.plan(self.chat, user_text)
        stages.append("chat_plan")

        graph_enriched = self._graph_context(plan["reasoning_query"])
        stages.append("graph_context")

        _, ranked, selected = self._compete_hypotheses(graph_enriched)
        stages.append("competition")

        parallel_result = {
            "branches": [],
            "winner": None,
            "used_budget": 0,
            "total_budget": self.parallel.total_budget,
            "stop_reason": "turn_timeout_before_parallel",
            "elapsed_seconds": 0.0,
        }

        if not turn_deadline.expired:
            # Never let parallel exploration receive more time than remains in this turn.
            original_parallel_timeout = self.parallel.parallel_seconds
            self.parallel.parallel_seconds = min(
                original_parallel_timeout,
                max(0.05, turn_deadline.remaining),
            )
            parallel_result = self.parallel.run(self, selected)
            self.parallel.parallel_seconds = original_parallel_timeout
            stages.append("parallel_search")

        enriched = graph_enriched
        if parallel_result.get("winner"):
            w = parallel_result["winner"]
            enriched += (
                "\n[並列探索トップ候補] "
                f'{w["subject"]} {w["relation"]} {w["object"]}'
                f' [score={w["score"]:.2f}, cycles={w["cycles"]}]'
            )

        reasoning_state = None
        reasoning_stop = "not_needed"

        if plan["needs_reasoning"]:
            if turn_deadline.expired:
                reasoning_stop = "turn_timeout_before_final_reasoning"
            else:
                reasoning_state = self.think_recursive(enriched)
                stages.append("final_reasoning")
                reasoning_stop = (
                    "turn_timeout_after_reasoning"
                    if turn_deadline.expired
                    else "completed"
                )

        reply = self.chat_verbalizer.render(
            user_text, plan, reasoning_state, self.chat
        )

        # If turn expired, explicitly keep the best partial result instead of failing.
        if turn_deadline.expired and reasoning_state is None:
            w = parallel_result.get("winner")
            if w:
                reply += (
                    "\n時間上限に達したため、途中の最良候補を返しています。"
                )
            else:
                reply += (
                    "\n時間上限に達したため、会話文脈のみで返しています。"
                )

        self.chat.add("assistant", reply)
        self.chat.remember_reply(reply)

        gc_report = self.gc.on_turn(self)
        stages.append("gc")

        if turn_deadline.expired:
            turn_status = "timeout"
        elif parallel_result.get("stop_reason") == "parallel_timeout":
            turn_status = "partial"
        else:
            turn_status = "completed"

        return {
            "version": "V49",
            "user_text": user_text,
            "learned": learned,
            "competition": [asdict(x) for x in ranked],
            "selected_for_parallel": [asdict(x) for x in selected],
            "parallel_search": parallel_result,
            "turn_timeout_seconds": self.timeout_policy.turn_seconds,
            "turn_elapsed_seconds": round(turn_deadline.elapsed, 4),
            "turn_status": turn_status,
            "reasoning_stop": reasoning_stop,
            "completed_stages": stages,
            "topic": self.chat.topic,
            "used_reasoning": reasoning_state is not None,
            "reply": reply,
            "reasoning": reasoning_state,
            "conversation_turns": len(self.chat.turns),
            "gc": gc_report,
            "memory_metrics": asdict(self.gc.metrics(self)),
        }

def main_v49():
    fap = FAPV49()
    print("FAP V49 TIMEOUT GUARD")
    print(
        "defaults: branch=0.75s / parallel=2.50s / turn=4.00s"
    )
    print(
        "commands: :json <text> | :timeouts | :parallel | :rank | "
        ":gc | :gcstat | :history | :quit"
    )
    last = None

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break

        if q == ":timeouts":
            print(json.dumps(
                asdict(fap.timeout_policy),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":parallel":
            print(json.dumps(
                last.get("parallel_search", {}) if last else {},
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":rank":
            print(json.dumps(
                last.get("competition", []) if last else [],
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":gc":
            print(json.dumps(
                fap.gc.collect(fap, force_level="hard"),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":gcstat":
            print(json.dumps(
                asdict(fap.gc.metrics(fap)),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue

        if q.startswith(":json "):
            last = fap.chat_once(q[6:])
            print(json.dumps(last, ensure_ascii=False, indent=2))
            continue

        last = fap.chat_once(q)
        print("FAP> " + last["reply"])
        print(
            f'FAP[time]> turn={last["turn_elapsed_seconds"]:.3f}s '
            f'status={last["turn_status"]} '
            f'parallel={last["parallel_search"].get("stop_reason")}'
        )


# ============================================================
# FAP V50 - PAGED / HOT-COLD MEMORY
# ============================================================

COLD_MEMORY_FILE = Path(__file__).with_name("fap_v50_cold_memory.json")

@dataclass
class ColdMemoryItem:
    text: str
    weight: float
    source: str
    accesses: int = 0
    last_score: float = 0.0

class PagedMemory:
    """
    Keep a small hot set in RAM and the rest on disk.
    Relevant cold items are faulted back into RAM on demand.
    """

    def __init__(
        self,
        hot_limit: int = 64,
        cold_limit: int = 4096,
        page_in_k: int = 8,
    ):
        self.hot_limit = max(16, int(hot_limit))
        self.cold_limit = max(self.hot_limit, int(cold_limit))
        self.page_in_k = max(1, int(page_in_k))
        self.cold: list[ColdMemoryItem] = []
        self.load()

    def load(self):
        if not COLD_MEMORY_FILE.exists():
            return
        try:
            raw = json.loads(COLD_MEMORY_FILE.read_text(encoding="utf-8"))
            self.cold = [ColdMemoryItem(**x) for x in raw.get("cold", [])][-self.cold_limit:]
        except Exception:
            self.cold = []

    def save(self):
        COLD_MEMORY_FILE.write_text(
            json.dumps(
                {"cold": [asdict(x) for x in self.cold[-self.cold_limit:]]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _key(text: str) -> str:
        return canon_text(text)

    def page_out(self, memory: list[MemoryItem]) -> tuple[list[MemoryItem], int]:
        """
        Keep strongest hot items. Move weaker/older items to cold storage.
        """
        if len(memory) <= self.hot_limit:
            return memory, 0

        # Stable score: weight + source importance.
        def hot_value(m):
            bonus = 0.20 if m.source in ("concept", "v44_graph") else 0.0
            return float(m.weight) + bonus

        ranked = sorted(enumerate(memory), key=lambda x: hot_value(x[1]), reverse=True)
        keep_idx = {i for i, _ in ranked[:self.hot_limit]}

        hot, moved = [], 0
        existing = {self._key(x.text): x for x in self.cold}

        for i, m in enumerate(memory):
            if i in keep_idx:
                hot.append(m)
                continue

            k = self._key(m.text)
            if k in existing:
                c = existing[k]
                c.weight = max(c.weight, float(m.weight))
                c.accesses += 1
            else:
                c = ColdMemoryItem(
                    text=m.text,
                    weight=float(m.weight),
                    source=m.source,
                    accesses=0,
                    last_score=0.0,
                )
                self.cold.append(c)
                existing[k] = c
            moved += 1

        if len(self.cold) > self.cold_limit:
            # Prefer keeping frequently accessed and higher weight cold items.
            self.cold.sort(
                key=lambda x: (x.accesses, x.weight, x.last_score),
                reverse=True,
            )
            self.cold = self.cold[:self.cold_limit]

        self.save()
        return hot, moved

    def page_in(self, query: str, hot: list[MemoryItem]) -> tuple[list[MemoryItem], list[dict]]:
        if not self.cold:
            return hot, []

        hot_keys = {self._key(m.text) for m in hot}
        scored = []
        for c in self.cold:
            if self._key(c.text) in hot_keys:
                continue
            s = similarity(query, c.text) * max(0.05, c.weight)
            if s > 0.05:
                scored.append((s, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected = scored[:self.page_in_k]

        loaded = []
        for score, c in selected:
            c.accesses += 1
            c.last_score = float(score)
            hot.append(MemoryItem(c.text, c.weight, "paged:" + c.source))
            loaded.append({
                "text": c.text,
                "score": round(float(score), 4),
                "accesses": c.accesses,
            })

        # Keep hot memory bounded after page-in.
        if len(hot) > self.hot_limit:
            # Prefer newly paged relevant items + high-weight persistent memory.
            def value(m):
                rel = similarity(query, m.text)
                src_bonus = 0.15 if m.source.startswith("paged:") else 0.0
                return rel + 0.35 * float(m.weight) + src_bonus
            hot = sorted(hot, key=value, reverse=True)[:self.hot_limit]

        self.save()
        return hot, loaded

    def stats(self, hot_count: int) -> dict:
        return {
            "hot_items": int(hot_count),
            "hot_limit": self.hot_limit,
            "cold_items": len(self.cold),
            "cold_limit": self.cold_limit,
            "page_in_k": self.page_in_k,
        }

class FAPV50(FAPV49):
    def __init__(
        self,
        max_cycles=4,
        min_improvement=0.025,
        gc_capacity=512,
        verification_budget=3,
        parallel_budget=12,
        max_parallel_branches=4,
        branch_timeout=0.75,
        parallel_timeout=2.50,
        turn_timeout=4.00,
        hot_memory_limit=64,
        cold_memory_limit=4096,
        page_in_k=8,
    ):
        super().__init__(
            max_cycles=max_cycles,
            min_improvement=min_improvement,
            gc_capacity=gc_capacity,
            verification_budget=verification_budget,
            parallel_budget=parallel_budget,
            max_parallel_branches=max_parallel_branches,
            branch_timeout=branch_timeout,
            parallel_timeout=parallel_timeout,
            turn_timeout=turn_timeout,
        )
        self.paged_memory = PagedMemory(
            hot_limit=hot_memory_limit,
            cold_limit=cold_memory_limit,
            page_in_k=page_in_k,
        )

    def _prepare_memory(self, query: str):
        # Page out before retrieval, then bring back only relevant cold items.
        self.memory, moved = self.paged_memory.page_out(self.memory)
        self.memory, loaded = self.paged_memory.page_in(query, self.memory)
        return {
            "paged_out": moved,
            "paged_in": loaded,
            "stats": self.paged_memory.stats(len(self.memory)),
        }

    def chat_once(self, user_text: str) -> dict:
        paging = self._prepare_memory(user_text)

        result = super().chat_once(user_text)
        result["version"] = "V50"
        result["paging"] = paging
        result["memory_residency"] = self.paged_memory.stats(len(self.memory))

        # Post-turn spill keeps RAM usage small even after learning.
        self.memory, moved_after = self.paged_memory.page_out(self.memory)
        result["paging"]["paged_out_after_turn"] = moved_after
        result["memory_residency"] = self.paged_memory.stats(len(self.memory))
        return result

def main_v50():
    fap = FAPV50()
    print("FAP V50 PAGED MEMORY")
    print("defaults: hot=64 / cold=4096 / page-in=8")
    print(
        "commands: :json <text> | :memstat | :cold | :timeouts | "
        ":gc | :gcstat | :history | :quit"
    )

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not q:
            continue
        if q in (":q", ":quit", "exit", "quit"):
            break

        if q == ":memstat":
            print(json.dumps(
                fap.paged_memory.stats(len(fap.memory)),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":cold":
            print(json.dumps(
                [asdict(x) for x in fap.paged_memory.cold[-50:]],
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":timeouts":
            print(json.dumps(asdict(fap.timeout_policy), ensure_ascii=False, indent=2))
            continue

        if q == ":gc":
            print(json.dumps(
                fap.gc.collect(fap, force_level="hard"),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":gcstat":
            print(json.dumps(
                asdict(fap.gc.metrics(fap)),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":history":
            for t in fap.chat.turns:
                print(f"{t.role}> {t.text}")
            continue

        if q.startswith(":json "):
            print(json.dumps(fap.chat_once(q[6:]), ensure_ascii=False, indent=2))
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])
        pg = result["paging"]
        print(
            f'FAP[mem]> hot={result["memory_residency"]["hot_items"]} '
            f'cold={result["memory_residency"]["cold_items"]} '
            f'loaded={len(pg["paged_in"])}'
        )


# ============================================================
# FAP V51 - WINDOWS SPEECH OUTPUT / "MOUTH"
# ============================================================

import os
import platform
import subprocess
import tempfile

VOICE_CONFIG_FILE = Path(__file__).with_name("fap_v51_voice.json")

@dataclass
class VoiceConfig:
    enabled: bool = True
    rate: int = 0          # System.Speech: -10 .. +10
    volume: int = 100      # 0 .. 100
    prefer_language: str = "ja-JP"
    voice_name: str = ""

class SpeechOutput:
    """
    Dependency-free Windows TTS front-end.

    - Uses Windows System.Speech through PowerShell.
    - Speech starts only AFTER cognition/reply generation.
    - Runs asynchronously so TTS does not consume reasoning timeout.
    - If Japanese voice is unavailable, Windows default voice is used.
    - If PowerShell/System.Speech is unavailable, text chat still works.
    """

    def __init__(self):
        self.config = VoiceConfig()
        self.process = None
        self.last_error = ""
        self.last_status = "idle"
        self.load()

    def load(self):
        if not VOICE_CONFIG_FILE.exists():
            return
        try:
            raw = json.loads(VOICE_CONFIG_FILE.read_text(encoding="utf-8"))
            self.config = VoiceConfig(**{
                k: raw[k] for k in asdict(self.config).keys() if k in raw
            })
        except Exception:
            pass

    def save(self):
        VOICE_CONFIG_FILE.write_text(
            json.dumps(asdict(self.config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        # Do not read internal diagnostic lines aloud.
        lines = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith(("FAP[", "[内部", "内部経路:", "経路:", "統合信頼度:")):
                continue
            lines.append(s)

        cleaned = "。".join(lines)
        cleaned = re.sub(r"https?://\S+", "URL", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:3000]

    @staticmethod
    def _powershell_exe():
        for exe in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
            try:
                # Windows PATH lookup; on non-Windows this normally returns None.
                import shutil as _shutil
                p = _shutil.which(exe)
                if p:
                    return p
            except Exception:
                pass
        return None

    def available(self) -> bool:
        return platform.system().lower() == "windows" and bool(self._powershell_exe())

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.process = None
        self.last_status = "stopped"

    def set_enabled(self, enabled: bool):
        self.config.enabled = bool(enabled)
        if not enabled:
            self.stop()
        self.save()

    def set_rate(self, rate: int):
        self.config.rate = max(-10, min(10, int(rate)))
        self.save()

    def set_volume(self, volume: int):
        self.config.volume = max(0, min(100, int(volume)))
        self.save()

    def set_voice(self, name: str):
        self.config.voice_name = str(name).strip()
        self.save()

    def list_voices(self) -> list[dict]:
        if not self.available():
            return []

        exe = self._powershell_exe()
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.GetInstalledVoices() | ForEach-Object { "
            "$i=$_.VoiceInfo; "
            "[PSCustomObject]@{Name=$i.Name; Culture=$i.Culture.Name; Gender=$i.Gender.ToString()} "
            "} | ConvertTo-Json -Compress"
        )
        try:
            cp = subprocess.run(
                [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if cp.returncode != 0:
                self.last_error = cp.stderr.strip()
                return []
            raw = cp.stdout.strip()
            if not raw:
                return []
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            return list(data)
        except Exception as ex:
            self.last_error = str(ex)
            return []

    def _select_voice_name(self) -> str:
        if self.config.voice_name:
            return self.config.voice_name

        voices = self.list_voices()
        wanted = self.config.prefer_language.lower()
        for v in voices:
            if str(v.get("Culture", "")).lower() == wanted:
                return str(v.get("Name", ""))
        for v in voices:
            if str(v.get("Culture", "")).lower().startswith("ja"):
                return str(v.get("Name", ""))
        return ""

    def speak(self, text: str) -> dict:
        cleaned = self._clean_text(text)

        if not self.config.enabled:
            return {"spoken": False, "status": "disabled"}

        if not cleaned:
            return {"spoken": False, "status": "empty"}

        if not self.available():
            self.last_status = "unavailable"
            return {
                "spoken": False,
                "status": "unavailable",
                "reason": "Windows PowerShell/System.Speech is required",
            }

        # Stop previous utterance rather than stacking stale replies.
        self.stop()

        exe = self._powershell_exe()
        voice_name = self._select_voice_name()

        # Pass text via temporary UTF-8 file to avoid shell quoting problems.
        fd, text_path = tempfile.mkstemp(prefix="fap_speech_", suffix=".txt")
        os.close(fd)
        Path(text_path).write_text(cleaned, encoding="utf-8")

        # Escape only fixed metadata, never the actual spoken text.
        ps_voice = voice_name.replace("'", "''")
        ps_path = str(text_path).replace("'", "''")
        rate = int(self.config.rate)
        volume = int(self.config.volume)

        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate={rate}; $s.Volume={volume}; "
        )
        if ps_voice:
            script += f"try {{$s.SelectVoice('{ps_voice}')}} catch {{}}; "

        script += (
            f"$t=[IO.File]::ReadAllText('{ps_path}', [Text.Encoding]::UTF8); "
            "try {$s.Speak($t)} finally {"
            f"Remove-Item -LiteralPath '{ps_path}' -Force -ErrorAction SilentlyContinue"
            "}"
        )

        try:
            self.process = subprocess.Popen(
                [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.last_status = "speaking"
            return {
                "spoken": True,
                "status": "speaking",
                "voice": voice_name or "Windows default",
                "rate": rate,
                "volume": volume,
            }
        except Exception as ex:
            self.last_error = str(ex)
            self.last_status = "error"
            try:
                Path(text_path).unlink(missing_ok=True)
            except Exception:
                pass
            return {
                "spoken": False,
                "status": "error",
                "reason": str(ex),
            }

    def status(self) -> dict:
        active = bool(self.process is not None and self.process.poll() is None)
        if active:
            self.last_status = "speaking"
        elif self.last_status == "speaking":
            self.last_status = "idle"

        return {
            **asdict(self.config),
            "available": self.available(),
            "status": self.last_status,
            "last_error": self.last_error,
        }

class FAPV51(FAPV50):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.speech = SpeechOutput()

    def chat_once(self, user_text: str) -> dict:
        result = super().chat_once(user_text)
        result["version"] = "V51"

        # Critical: speech happens AFTER the reasoning/chat result exists,
        # so TTS never blocks the cognitive timeout.
        voice_result = self.speech.speak(result["reply"])
        result["voice"] = voice_result
        return result

def main_v51():
    fap = FAPV51()
    print("FAP V51 SPEECH OUTPUT")
    print("Windows TTS / Japanese voice preferred / async speech")
    print(
        "commands: :voice on|off | :voices | :rate -10..10 | "
        ":volume 0..100 | :stop | :voicestat | :memstat | :timeouts | :quit"
    )

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            fap.speech.stop()
            print()
            break

        if not q:
            continue

        if q in (":q", ":quit", "exit", "quit"):
            fap.speech.stop()
            break

        if q == ":voice on":
            fap.speech.set_enabled(True)
            print("FAP> voice=on")
            continue

        if q == ":voice off":
            fap.speech.set_enabled(False)
            print("FAP> voice=off")
            continue

        if q == ":stop":
            fap.speech.stop()
            print("FAP> speech stopped")
            continue

        if q == ":voices":
            print(json.dumps(fap.speech.list_voices(), ensure_ascii=False, indent=2))
            continue

        if q.startswith(":rate "):
            try:
                fap.speech.set_rate(int(q.split(maxsplit=1)[1]))
                print("FAP> rate=" + str(fap.speech.config.rate))
            except Exception:
                print("FAP> rate must be -10..10")
            continue

        if q.startswith(":volume "):
            try:
                fap.speech.set_volume(int(q.split(maxsplit=1)[1]))
                print("FAP> volume=" + str(fap.speech.config.volume))
            except Exception:
                print("FAP> volume must be 0..100")
            continue

        if q == ":voicestat":
            print(json.dumps(fap.speech.status(), ensure_ascii=False, indent=2))
            continue

        if q == ":memstat":
            print(json.dumps(
                fap.paged_memory.stats(len(fap.memory)),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":timeouts":
            print(json.dumps(asdict(fap.timeout_policy), ensure_ascii=False, indent=2))
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])

        vr = result["voice"]
        print(
            f'FAP[voice]> status={vr.get("status")}'
            + (f' voice={vr.get("voice")}' if vr.get("voice") else "")
        )


# ============================================================
# FAP V52 - WINDOWS SPEECH INPUT + SPOKEN CONVERSATION
# ============================================================

import platform
import subprocess
import shutil as _shutil

@dataclass
class ListenConfig:
    enabled: bool = True
    language: str = "ja-JP"
    timeout_seconds: float = 6.0
    babble_seconds: float = 2.0

class SpeechInput:
    """
    Push-to-talk speech recognition using Windows System.Speech.
    Fallback is graceful when no compatible recognizer is installed.
    """

    def __init__(self):
        self.config = ListenConfig()
        self.last_error = ""
        self.last_status = "idle"

    @staticmethod
    def _powershell_exe():
        for exe in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
            p = _shutil.which(exe)
            if p:
                return p
        return None

    def available(self) -> bool:
        return platform.system().lower() == "windows" and bool(self._powershell_exe())

    def list_recognizers(self) -> list[dict]:
        if not self.available():
            return []

        exe = self._powershell_exe()
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "[System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() | "
            "ForEach-Object { "
            "[PSCustomObject]@{Id=$_.Id; Name=$_.Name; Culture=$_.Culture.Name; Description=$_.Description} "
            "} | ConvertTo-Json -Compress"
        )
        try:
            cp = subprocess.run(
                [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if cp.returncode != 0:
                self.last_error = cp.stderr.strip()
                return []
            raw = cp.stdout.strip()
            if not raw:
                return []
            data = json.loads(raw)
            return [data] if isinstance(data, dict) else list(data)
        except Exception as ex:
            self.last_error = str(ex)
            return []

    def listen_once(self) -> dict:
        if not self.config.enabled:
            return {"heard": False, "status": "disabled", "text": ""}

        if not self.available():
            self.last_status = "unavailable"
            return {
                "heard": False,
                "status": "unavailable",
                "text": "",
                "reason": "Windows PowerShell/System.Speech is required",
            }

        recs = self.list_recognizers()
        wanted = self.config.language.lower()
        rec = None

        for x in recs:
            if str(x.get("Culture", "")).lower() == wanted:
                rec = x
                break

        if rec is None:
            for x in recs:
                if str(x.get("Culture", "")).lower().startswith("ja"):
                    rec = x
                    break

        if rec is None and recs:
            rec = recs[0]

        if rec is None:
            self.last_status = "no_recognizer"
            return {
                "heard": False,
                "status": "no_recognizer",
                "text": "",
                "reason": "No Windows speech recognizer installed",
            }

        exe = self._powershell_exe()
        rec_id = str(rec.get("Id", "")).replace("'", "''")
        timeout = max(0.5, float(self.config.timeout_seconds))
        babble = max(0.2, float(self.config.babble_seconds))

        # SpeechRecognitionEngine(recognizerInfo) + DictationGrammar.
        script = (
            "Add-Type -AssemblyName System.Speech; "
            f"$ri=[System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() | "
            f"Where-Object {{$_.Id -eq '{rec_id}'}} | Select-Object -First 1; "
            "if(-not $ri){ exit 3 }; "
            "$r=New-Object System.Speech.Recognition.SpeechRecognitionEngine($ri); "
            "$r.SetInputToDefaultAudioDevice(); "
            "$r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
            f"$r.BabbleTimeout=[TimeSpan]::FromSeconds({babble}); "
            f"$res=$r.Recognize([TimeSpan]::FromSeconds({timeout})); "
            "if($res){ "
            "[PSCustomObject]@{Text=$res.Text; Confidence=$res.Confidence; "
            "Culture=$ri.Culture.Name; Recognizer=$ri.Name} | ConvertTo-Json -Compress "
            "} "
        )

        self.last_status = "listening"
        try:
            cp = subprocess.run(
                [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=timeout + 3.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            raw = cp.stdout.strip()

            if cp.returncode != 0:
                self.last_error = cp.stderr.strip()
                self.last_status = "error"
                return {
                    "heard": False,
                    "status": "error",
                    "text": "",
                    "reason": self.last_error or f"exit={cp.returncode}",
                }

            if not raw:
                self.last_status = "timeout"
                return {
                    "heard": False,
                    "status": "timeout",
                    "text": "",
                    "recognizer": rec.get("Name", ""),
                }

            data = json.loads(raw)
            text = str(data.get("Text", "")).strip()
            conf = float(data.get("Confidence", 0.0))

            if not text:
                self.last_status = "empty"
                return {
                    "heard": False,
                    "status": "empty",
                    "text": "",
                }

            self.last_status = "heard"
            return {
                "heard": True,
                "status": "heard",
                "text": text,
                "confidence": round(conf, 4),
                "culture": data.get("Culture", ""),
                "recognizer": data.get("Recognizer", ""),
            }

        except subprocess.TimeoutExpired:
            self.last_status = "timeout"
            return {
                "heard": False,
                "status": "timeout",
                "text": "",
            }
        except Exception as ex:
            self.last_error = str(ex)
            self.last_status = "error"
            return {
                "heard": False,
                "status": "error",
                "text": "",
                "reason": str(ex),
            }

class FAPV52(FAPV51):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.speech_input = SpeechInput()

    def voice_turn(self) -> dict:
        heard = self.speech_input.listen_once()

        if not heard.get("heard"):
            return {
                "version": "V52",
                "input": heard,
                "chat": None,
                "status": heard.get("status", "no_input"),
            }

        # Important: recognized text goes through the exact same chat/reasoning
        # pipeline as keyboard input.
        chat = self.chat_once(heard["text"])
        return {
            "version": "V52",
            "input": heard,
            "chat": chat,
            "status": "completed",
        }

def main_v52():
    fap = FAPV52()
    print("FAP V52 VOICE CONVERSATION")
    print("Push-to-talk speech input + spoken reply")
    print(
        "commands: :listen | :recognizers | :voice on|off | :voices | "
        ":rate -10..10 | :volume 0..100 | :stop | :memstat | :quit"
    )

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            fap.speech.stop()
            print()
            break

        if not q:
            continue

        if q in (":q", ":quit", "exit", "quit"):
            fap.speech.stop()
            break

        if q == ":listen":
            print("FAP> listening...")
            result = fap.voice_turn()
            inp = result["input"]

            if not inp.get("heard"):
                print(
                    "FAP[input]> "
                    + str(inp.get("status"))
                    + (": " + str(inp.get("reason")) if inp.get("reason") else "")
                )
                continue

            print(
                f'You[voice]> {inp["text"]}'
                f' (confidence={inp.get("confidence", 0):.2f})'
            )
            chat = result["chat"]
            print("FAP> " + chat["reply"])
            print(
                "FAP[voice]> status="
                + str(chat["voice"].get("status"))
            )
            continue

        if q == ":recognizers":
            print(json.dumps(
                fap.speech_input.list_recognizers(),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":voice on":
            fap.speech.set_enabled(True)
            print("FAP> voice=on")
            continue

        if q == ":voice off":
            fap.speech.set_enabled(False)
            print("FAP> voice=off")
            continue

        if q == ":voices":
            print(json.dumps(
                fap.speech.list_voices(),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q.startswith(":rate "):
            try:
                fap.speech.set_rate(int(q.split(maxsplit=1)[1]))
                print("FAP> rate=" + str(fap.speech.config.rate))
            except Exception:
                print("FAP> rate must be -10..10")
            continue

        if q.startswith(":volume "):
            try:
                fap.speech.set_volume(int(q.split(maxsplit=1)[1]))
                print("FAP> volume=" + str(fap.speech.config.volume))
            except Exception:
                print("FAP> volume must be 0..100")
            continue

        if q == ":stop":
            fap.speech.stop()
            print("FAP> speech stopped")
            continue

        if q == ":memstat":
            print(json.dumps(
                fap.paged_memory.stats(len(fap.memory)),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])


# ============================================================
# FAP V53 - RICH / NATURAL / REDUNDANT CONVERSATION
# ============================================================

CHAT_STYLE_FILE = Path(__file__).with_name("fap_v53_chat_style.json")

@dataclass
class ChatStyle:
    mode: str = "rich"       # brief / normal / rich / verbose
    callback: bool = True
    examples: bool = True
    reasons: bool = True
    detours: bool = True
    max_paragraphs: int = 5

class NaturalConversationLayer:
    """
    Makes FAP less like terse Q&A and more like continuous conversation.
    It expands only after the underlying reasoning result is available.
    """

    def __init__(self):
        self.style = ChatStyle()
        self.load()

    def load(self):
        if not CHAT_STYLE_FILE.exists():
            return
        try:
            raw = json.loads(CHAT_STYLE_FILE.read_text(encoding="utf-8"))
            for k in asdict(self.style):
                if k in raw:
                    setattr(self.style, k, raw[k])
        except Exception:
            pass

    def save(self):
        CHAT_STYLE_FILE.write_text(
            json.dumps(asdict(self.style), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_mode(self, mode: str):
        if mode not in ("brief", "normal", "rich", "verbose"):
            return False
        self.style.mode = mode
        self.style.max_paragraphs = {
            "brief": 1,
            "normal": 2,
            "rich": 4,
            "verbose": 6,
        }[mode]
        self.save()
        return True

    @staticmethod
    def _recent_user_turns(chat, n=4):
        turns = []
        for t in reversed(chat.turns):
            if t.role == "user":
                turns.append(t.text.strip())
                if len(turns) >= n:
                    break
        return list(reversed(turns))

    @staticmethod
    def _clean_reply(reply: str) -> str:
        reply = re.sub(r"\n{3,}", "\n\n", reply).strip()
        return reply

    @staticmethod
    def _sentence_count(text: str) -> int:
        return len([x for x in re.split(r"[。！？!?]+", text) if x.strip()])

    def _callback(self, user_text: str, chat) -> str:
        prev = self._recent_user_turns(chat, 3)
        prev = [x for x in prev if x != user_text]
        if not prev:
            return ""

        last = prev[-1]
        if similarity(user_text, last) > 0.45:
            return "前の話の流れを引き継ぐと、"
        if any(x in user_text for x in ("それ", "その", "これ", "あれ", "さっき", "先ほど")):
            return "さっきの話につなげると、"
        return ""

    def _reason_phrase(self, result: dict) -> str:
        if not self.style.reasons:
            return ""

        reasoning = result.get("reasoning")
        if not isinstance(reasoning, dict):
            return ""

        conf = reasoning.get("confidence")
        frame = reasoning.get("frame", {})
        evidence = frame.get("evidence", []) if isinstance(frame, dict) else []
        conflicts = frame.get("conflicts", []) if isinstance(frame, dict) else []

        if conflicts:
            return (
                "このあたりは一つに決め打ちするより、"
                "矛盾している情報を残したまま比較する方が自然です。"
            )
        if evidence:
            return (
                "いまの判断は、直前までの会話と拾えている関連情報を"
                "まとめた上で出しています。"
            )
        if conf is not None and float(conf) < 0.45:
            return "ここはまだ根拠が薄いので、断定しすぎない方がよさそうです。"
        return ""

    def _example_phrase(self, user_text: str, result: dict) -> str:
        if not self.style.examples:
            return ""

        if any(k in user_text for k in ("どう", "どんな", "例えば", "例")):
            return ""

        topic = result.get("topic", "")
        if not topic:
            return ""

        return (
            f"たとえば「{topic}」について話を続ける場合も、"
            "結論だけで終わらず、理由や具体例までつないで返すようにできます。"
        )

    def _detour_phrase(self, user_text: str, result: dict) -> str:
        if not self.style.detours:
            return ""

        if len(user_text) < 4:
            return ""

        if any(k in user_text for k in ("ちなみに", "ところで", "余談", "脱線")):
            return (
                "こういう少し横道に入る話も、そのまま会話として保持して、"
                "あとで元の話題へ戻せるようにしておきます。"
            )
        return ""

    def enrich(self, user_text: str, base_reply: str, result: dict, chat) -> str:
        base = self._clean_reply(base_reply)
        mode = self.style.mode

        if mode == "brief":
            return base

        parts = []

        cb = self._callback(user_text, chat) if self.style.callback else ""
        if cb:
            # callback is a prefix, not a standalone filler.
            parts.append(cb + base)
        else:
            parts.append(base)

        if mode in ("rich", "verbose"):
            reason = self._reason_phrase(result)
            if reason and reason not in parts:
                parts.append(reason)

            example = self._example_phrase(user_text, result)
            if example and example not in parts:
                parts.append(example)

        if mode == "verbose":
            detour = self._detour_phrase(user_text, result)
            if detour:
                parts.append(detour)

            parts.append(
                "要するに、短く答えるだけではなく、必要なら少し回り道をしながら、"
                "前の文脈と今の話題をつないで会話を続ける方針です。"
            )

        # Avoid overgrowth and near-duplicate paragraphs.
        final = []
        for p in parts:
            if not p:
                continue
            if any(similarity(p, q) > 0.82 for q in final):
                continue
            final.append(p)
            if len(final) >= self.style.max_paragraphs:
                break

        return "\n\n".join(final)

class FAPV53(FAPV52):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.natural_chat = NaturalConversationLayer()

    def chat_once(self, user_text: str) -> dict:
        # Keep all prior cognition/memory/speech systems.
        result = super().chat_once(user_text)

        # Enrich AFTER the core reply is made, but BEFORE speaking it.
        # V52/V51 may already have triggered speech, so stop stale speech and
        # speak the final enriched form instead.
        old_reply = result.get("reply", "")
        enriched = self.natural_chat.enrich(
            user_text=user_text,
            base_reply=old_reply,
            result=result,
            chat=self.chat,
        )

        if enriched != old_reply:
            self.speech.stop()
            result["reply"] = enriched
            result["voice"] = self.speech.speak(enriched)

            # Replace the most recent assistant turn with enriched final reply.
            if self.chat.turns and self.chat.turns[-1].role == "assistant":
                self.chat.turns[-1].text = enriched
            self.chat.remember_reply(enriched)

        result["version"] = "V53"
        result["chat_style"] = asdict(self.natural_chat.style)
        return result

def main_v53():
    fap = FAPV53()
    print("FAP V53 RICH NATURAL CHAT")
    print("default style: rich")
    print(
        "commands: :brief | :normal | :rich | :verbose | :style | "
        ":listen | :voice on|off | :stop | :quit"
    )

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            fap.speech.stop()
            print()
            break

        if not q:
            continue

        if q in (":q", ":quit", "exit", "quit"):
            fap.speech.stop()
            break

        if q in (":brief", ":normal", ":rich", ":verbose"):
            mode = q[1:]
            fap.natural_chat.set_mode(mode)
            print("FAP> chat style=" + mode)
            continue

        if q == ":style":
            print(json.dumps(
                asdict(fap.natural_chat.style),
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q == ":listen":
            print("FAP> listening...")
            heard = fap.speech_input.listen_once()
            if not heard.get("heard"):
                print("FAP[input]> " + str(heard.get("status")))
                continue
            print(f'You[voice]> {heard["text"]}')
            result = fap.chat_once(heard["text"])
            print("FAP> " + result["reply"])
            continue

        if q == ":voice on":
            fap.speech.set_enabled(True)
            print("FAP> voice=on")
            continue

        if q == ":voice off":
            fap.speech.set_enabled(False)
            print("FAP> voice=off")
            continue

        if q == ":stop":
            fap.speech.stop()
            print("FAP> speech stopped")
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])


# ============================================================
# FAP V54 - DISTILLED CONVERSATION CIRCUITS
# Source: 5,000 synthetic Japanese conversation records
# Dataset is NOT required at runtime.
# ============================================================

V54_DISTILLED_CIRCUITS = json.loads(r"""{"rich_explanation":{"priority":0.8,"detect":["説明","教えて","詳しく","分かりやすく","理由","具体例","自然に","少し丁寧に","長く使いたい人向けに説明してください","速度を上げたい人向けに説明してください","軽量化したい人向けに説明してください","検証しやすくしたい人向けに説明してください","拡張しやすくしたい人向けに説明してください","実際に使いたい人向けに説明してください","失敗を減らしたい人向けに説明してください","判断を安定させたい人向けに説明してください"],"plan":["answer","reason","example","implication"],"max_extra":3,"dataset_weight":0.1,"target_chars":249,"target_sentences":5},"context_followup":{"priority":0.95,"detect":["それ","これ","その","さっき","前の","続き","もう少し","それをもう少し掘り下げてください","自然に話してください","少し丁寧に話してください","長く使いたいです","速度を上げたいです","軽量化したいです","検証しやすくしたいです","拡張しやすくしたいです","実際に使いたいです"],"plan":["resolve_context","answer","deepen"],"max_extra":2,"dataset_weight":0.1,"target_chars":181,"target_sentences":8},"constraint_aware":{"priority":0.88,"detect":["ただし","条件","制約","重視","増やしすぎ","遅くしすぎ","しつつ","自然に説明してください","少し丁寧に説明してください","長期利用で崩れにくいことも重視したいです","途中結果でも返せることも重視したいです","説明を単調にしないことも重視したいです","誤解を減らすことも重視したいです","文脈を切らさないことも重視したいです","応答を遅くしすぎないことも重視したいです","変更を戻せることも重視したいです"],"plan":["extract_constraint","answer_under_constraint","tradeoff"],"max_extra":2,"dataset_weight":0.1,"target_chars":182,"target_sentences":4},"conversation_repair":{"priority":1.0,"detect":["いや","違う","ではなく","そうじゃ","訂正","というより","詳しくお願いします","簡潔に直してください","会話っぽく直してください","お願いします","速度ではなくメモリ使用量のことです","自然さではなく正確さのことです","短さではなく説明量のことです","正確さではなく冗長さのことです","メモリ使用量ではなく応答速度のことです"],"plan":["replace_interpretation","answer_new_target"],"max_extra":1,"dataset_weight":0.1,"target_chars":140,"target_sentences":6},"ambiguity_resolution":{"priority":0.92,"detect":["あれ","それで","前のやつ","そのまま","どうなった","続けられ","自然に答えてください","少し丁寧に答えてください","続きはできますか","前の話とつながっていますか","前のやつを続けられますか","もっと良くできますか","もう少し詰められますか","それは残せますか","それで大丈夫ですか","それって重くないですか"],"plan":["link_recent_context","state_assumption","answer"],"max_extra":2,"dataset_weight":0.1,"target_chars":133,"target_sentences":4},"disagreement":{"priority":0.9,"detect":["ですよね","絶対","全部","一つだけ","必ず","長いほど","多いほど","率直にお願いします","古い情報は全部消した方がすっきりしますよね","全部一気に変えた方が早いですよね","候補は一つだけに絞った方がいいですよね","会話は長いほど自然になりますよね","タイムアウトは長いほど正確になりますよね","自然に答えてください","少し丁寧に答えてください","音声では"],"plan":["acknowledge_case","counterexample","balanced_rule"],"max_extra":2,"dataset_weight":0.1,"target_chars":180,"target_sentences":5},"detour_return":{"priority":0.86,"detect":["ちなみに","ところで","余談","本題","戻って","戻り","では本題に戻してください","自然にお願いします","少し丁寧にお願いします","も少し気になります","の話を続けましょう","音声の話を続けましょう","雑談の話を続けましょう","読書の話を続けましょう","自動化の話を続けましょう"],"plan":["hold_topic","detour","restore_topic"],"max_extra":2,"dataset_weight":0.1,"target_chars":126,"target_sentences":7},"uncertainty":{"priority":0.96,"detect":["分からない","不明","不確実","仮説","可能性","断定","情報が足り","まだ分からない部分があるならどう答えますか","自然にお願いします","少し丁寧にお願いします","長く使いたい前提で","速度を上げたい前提で","軽量化したい前提で","検証しやすくしたい前提で","拡張しやすくしたい前提で","実際に使いたい前提で"],"plan":["separate_fact_guess","keep_candidates","state_uncertainty"],"max_extra":2,"dataset_weight":0.1,"target_chars":169,"target_sentences":4},"smalltalk":{"priority":0.6,"detect":["面白い","雑談","話しましょう","奥が","気になります","好き","自然に続けてください","少し丁寧に続けてください","って話していると広がりますね","って考えるほど奥がありますね","って意外と面白いですね","って少しゆっくり話したいです","って別の角度も気になります","ってもう少し雑談したいです","ってまだ話せそうですね","ってなんか続けたくなりますね"],"plan":["acknowledge","expand_topic","leave_opening"],"max_extra":2,"dataset_weight":0.1,"target_chars":131,"target_sentences":4},"long_form":{"priority":0.78,"detect":["長め","冗長","詳しく","深く","じっくり","短くなくて","自然に長めに考えてください","少し丁寧に長めに考えてください","長く使いたいという視点で","速度を上げたいという視点で","軽量化したいという視点で","検証しやすくしたいという視点で","拡張しやすくしたいという視点で","実際に使いたいという視点で","失敗を減らしたいという視点で","判断を安定させたいという視点で"],"plan":["answer","reason","example","contrast","summary"],"max_extra":4,"dataset_weight":0.1,"target_chars":262,"target_sentences":5}}""")
V54_DISTILLATION_REPORT = json.loads(r"""{"source_records":5000,"source_categories":10,"circuits":10,"categories":{"ambiguity_resolution":{"weight":0.1,"count":500,"avg_chars":132.7,"avg_messages":4,"avg_sentences":4,"avg_paragraphs":1,"cues":["自然に答えてください","少し丁寧に答えてください","続きはできますか","前の話とつながっていますか","前のやつを続けられますか","もっと良くできますか","もう少し詰められますか","それは残せますか","それで大丈夫ですか","それって重くないですか"],"motifs":["速度","自然さ","省メモリでは対策が違うので","安定性","今の文脈では一番影響の大きい点から小さく変更して確認するのが良いです","まず改善したい軸を一つ決めると進めやすいです","ただ","そのまま続けられます"]},"constraint_aware":{"weight":0.1,"count":500,"avg_chars":181.7,"avg_messages":2,"avg_sentences":4,"avg_paragraphs":1,"cues":["自然に説明してください","少し丁寧に説明してください","長期利用で崩れにくいことも重視したいです","途中結果でも返せることも重視したいです","説明を単調にしないことも重視したいです","誤解を減らすことも重視したいです","文脈を切らさないことも重視したいです","応答を遅くしすぎないことも重視したいです","変更を戻せることも重視したいです","候補を増やしすぎないことも重視したいです"],"motifs":["途中で方針がぶれにくくなります","良い結果を出すことと","特に長く使う仕組みでは","残った候補だけを小さく試します","改善案をいくつか出しても","性能だけを見て後から作り直すより","壊れにくいことを別々に評価するのが有効です","制約を破る案は先に外し"]},"context_followup":{"weight":0.1,"count":500,"avg_chars":181.3,"avg_messages":6,"avg_sentences":8,"avg_paragraphs":1,"cues":["それをもう少し掘り下げてください","自然に話してください","少し丁寧に話してください","長く使いたいです","速度を上げたいです","軽量化したいです","検証しやすくしたいです","拡張しやすくしたいです","実際に使いたいです","失敗を減らしたいです"],"motifs":["直前の文脈を保ったまま詳しくすることで","改善余地の順に分けると理解しやすいです","失敗条件","別の話題に飛ばず自然に深掘りできます","まず今の目的をそろえると話しやすいです","ここでの","いいですね","長く使いたいという前提で"]},"conversation_repair":{"weight":0.1,"count":500,"avg_chars":140.0,"avg_messages":4,"avg_sentences":6,"avg_paragraphs":1,"cues":["いや","詳しくお願いします","簡潔に直してください","会話っぽく直してください","お願いします","速度ではなくメモリ使用量のことです","自然さではなく正確さのことです","短さではなく説明量のことです","正確さではなく冗長さのことです","メモリ使用量ではなく応答速度のことです"],"motifs":["訂正が入った場合は","直近の修正を優先する方が自然です","古い解釈を引きずらず","なるほど","それなら前提を切り替えます","説明量に効く変更だけを考えます","正確さに効く変更だけを考えます","応答速度に効く変更だけを考えます"]},"detour_return":{"weight":0.1,"count":500,"avg_chars":126.0,"avg_messages":6,"avg_sentences":7,"avg_paragraphs":1,"cues":["では本題に戻してください","自然にお願いします","少し丁寧にお願いします","も少し気になります","の話を続けましょう","ちなみに","音声の話を続けましょう","雑談の話を続けましょう","読書の話を続けましょう","自動化の話を続けましょう"],"motifs":["戻ります","少し横道に入ると","前の前提を残したまま進めます","本題は","別の角度から","を見る材料になります","も関係がありますね","の話は補助情報として残しつつ"]},"disagreement":{"weight":0.1,"count":500,"avg_chars":179.8,"avg_messages":2,"avg_sentences":5,"avg_paragraphs":1,"cues":["率直にお願いします","古い情報は全部消した方がすっきりしますよね","全部一気に変えた方が早いですよね","候補は一つだけに絞った方がいいですよね","会話は長いほど自然になりますよね","タイムアウトは長いほど正確になりますよね","自然に答えてください","少し丁寧に答えてください","音声では","雑談では"],"motifs":["検証できる単位で調整するのが良いです","情報を消しすぎると後で再確認できなくなります","弱いものを早めに切る方が現実的です","常にそうとは限りません","少数の候補を比較し","単純化しすぎると別の問題が出ることがあります","例えば変更をまとめすぎると原因を追いにくくなり","二択にせず"]},"long_form":{"weight":0.1,"count":500,"avg_chars":262.4,"avg_messages":2,"avg_sentences":5,"avg_paragraphs":1,"cues":["自然に長めに考えてください","少し丁寧に長めに考えてください","長く使いたいという視点で","速度を上げたいという視点で","軽量化したいという視点で","検証しやすくしたいという視点で","拡張しやすくしたいという視点で","実際に使いたいという視点で","失敗を減らしたいという視点で","判断を安定させたいという視点で"],"motifs":["長期間使い続ける仕組みでは","検証しやすさや戻しやすさも大事になります","最初に単純な結論を置くより","性能を上げることと同じくらい","必要な安定性や記憶管理が変わります","実際の使い方では制約や失敗条件も一緒に見ます","例えば短時間だけ動けばよい仕組みと","何を誤解したかを記録しておくと次の改善につながります"]},"rich_explanation":{"weight":0.1,"count":500,"avg_chars":249.4,"avg_messages":2,"avg_sentences":5,"avg_paragraphs":1,"cues":["自然に","少し丁寧に","長く使いたい人向けに説明してください","速度を上げたい人向けに説明してください","軽量化したい人向けに説明してください","検証しやすくしたい人向けに説明してください","拡張しやすくしたい人向けに説明してください","実際に使いたい人向けに説明してください","失敗を減らしたい人向けに説明してください","判断を安定させたい人向けに説明してください"],"motifs":["長く使う場合は性能だけでなく","目的に応じて見方を切り替えられるように理解する方が実用的です","最初から全部を最適化するより","戻し方や記録","小さな変更を一つ入れて結果を見た方が","実際の使い方","失敗しやすい条件の順に分けると話が飛びにくくなります","例外処理も含めて考えると安定します"]},"smalltalk":{"weight":0.1,"count":500,"avg_chars":130.6,"avg_messages":2,"avg_sentences":4,"avg_paragraphs":1,"cues":["自然に続けてください","少し丁寧に続けてください","って話していると広がりますね","って考えるほど奥がありますね","って意外と面白いですね","って少しゆっくり話したいです","って別の角度も気になります","ってもう少し雑談したいです","ってまだ話せそうですね","ってなんか続けたくなりますね"],"motifs":["話していくと別の観点が出てきます","無理に結論へ急がず","最初は一つの話題に見えても","実際に使う場面を想像するとさらに話が増えます","前の話を拾いながら少しずつ広げる方が自然です","そうですね","こういう雑談では","音声は"]},"uncertainty":{"weight":0.1,"count":500,"avg_chars":168.7,"avg_messages":2,"avg_sentences":4,"avg_paragraphs":1,"cues":["まだ分からない部分があるならどう答えますか","自然にお願いします","少し丁寧にお願いします","長く使いたい前提で","速度を上げたい前提で","軽量化したい前提で","検証しやすくしたい前提で","拡張しやすくしたい前提で","実際に使いたい前提で","失敗を減らしたい前提で"],"motifs":["間違った確信を持つ危険は減ります","追加情報が来たときに比較できる形にしておく方が安全です","複数の説明があり得る場合も","確定している事実と推測を分け","断定は弱くなりますが","推測は候補として残します","分からない部分を無理に埋めない方が良いです","一つに決め打ちせず"]}}}""")

class DistilledConversationOrgan:
    """
    Runtime representation of the V53 dataset distillation.

    Important:
    - No 5,000-row dataset is loaded at runtime.
    - The dataset has been reduced to compact conversation circuits,
      learned cue lists, target response statistics, and priorities.
    - This is behavioral distillation, not neural-network weight distillation.
    """

    def __init__(self):
        self.circuits = V54_DISTILLED_CIRCUITS
        self.report = V54_DISTILLATION_REPORT

    @staticmethod
    def _norm(text: str) -> str:
        return re.sub(r"\s+", "", (text or "").lower())

    @staticmethod
    def _recent_user_text(chat, skip_current=True) -> str:
        users = [t.text for t in chat.turns if getattr(t, "role", "") == "user"]
        if skip_current and users:
            users = users[:-1]
        return users[-1] if users else ""

    @staticmethod
    def _extract_repair_target(text: str) -> str:
        # Typical Japanese correction:
        # "AではなくB", "AじゃなくB", "AじゃなくてB"
        patterns = [
            r"ではなく[、, ]*([^。！？!?]+)",
            r"じゃなくて?[、, ]*([^。！？!?]+)",
            r"というより[、, ]*([^。！？!?]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                target = m.group(1).strip()
                target = re.sub(r"(のこと|です|だよ|ですね|なんです)$", "", target).strip()
                return target[:80]
        return ""

    def score(self, user_text: str, chat=None) -> list[dict]:
        norm = self._norm(user_text)
        scored = []

        for name, spec in self.circuits.items():
            hits = []
            score = float(spec.get("dataset_weight", 0.0)) * 0.20

            for cue in spec.get("detect", []):
                c = self._norm(cue)
                if c and c in norm:
                    hits.append(cue)
                    score += 1.0

            score *= float(spec.get("priority", 1.0))

            # Structural boosts.
            if name == "conversation_repair" and re.search(
                r"(ではなく|じゃなく|違う|訂正|そうじゃ)", user_text
            ):
                score += 3.0

            if name == "context_followup" and re.search(
                r"(それ|これ|その|さっき|前の|続き|もう少し)", user_text
            ):
                score += 1.5

            if name == "long_form" and re.search(
                r"(長め|冗長|詳しく|深く|じっくり|短くなく)", user_text
            ):
                score += 2.0

            if name == "uncertainty" and re.search(
                r"(分から|不明|不確実|仮説|可能性|断定|情報.*足り)", user_text
            ):
                score += 2.0

            if name == "detour_return" and re.search(
                r"(ちなみに|ところで|本題|戻)", user_text
            ):
                score += 2.0

            if name == "constraint_aware" and re.search(
                r"(ただし|制約|条件|重視|しすぎない|ながら|つつ)", user_text
            ):
                score += 1.5

            if name == "disagreement" and re.search(
                r"(ですよね|絶対|全部|一つだけ|必ず|ほど)", user_text
            ):
                score += 1.0

            if score > 0.25:
                scored.append({
                    "name": name,
                    "score": round(score, 4),
                    "hits": hits[:6],
                    "plan": list(spec.get("plan", [])),
                    "target_chars": spec.get("target_chars", 220),
                    "target_sentences": spec.get("target_sentences", 4),
                })

        scored.sort(key=lambda x: x["score"], reverse=True)

        # Correction takes control when explicit.
        if scored and scored[0]["name"] == "conversation_repair":
            return scored[:2]

        return scored[:3]

    def _context_line(self, user_text: str, chat) -> str:
        prev = self._recent_user_text(chat, skip_current=True)
        if not prev:
            return ""
        if re.search(r"(それ|これ|その|前の|さっき|続き)", user_text):
            topic = prev.strip().replace("\n", " ")
            if len(topic) > 80:
                topic = topic[:77] + "..."
            return f"直前の「{topic}」という文脈を引き継いで考えます。"
        return ""

    def _repair_line(self, user_text: str) -> str:
        target = self._extract_repair_target(user_text)
        if target:
            return f"訂正を優先します。ここからは「{target}」を新しい前提として扱います。"
        return "訂正を優先して、直前の解釈より今回の言い直しを新しい前提として扱います。"

    @staticmethod
    def _constraint_line(user_text: str) -> str:
        if re.search(r"(メモリ|RAM|容量)", user_text, re.I):
            return "その条件では、性能だけでなく常駐メモリと保存量も別々に評価します。"
        if re.search(r"(速度|遅|時間|タイムアウト)", user_text):
            return "その条件では、精度だけでなく応答時間の上限も同時に守る必要があります。"
        return "その条件を後付けにせず、最初から判断基準の一つとして扱います。"

    @staticmethod
    def _uncertainty_line() -> str:
        return "確定している部分と推測を分け、根拠が足りない部分は仮説のまま残します。"

    @staticmethod
    def _disagreement_line() -> str:
        return "一つのやり方に固定せず、成立する場合と失敗する場合を分けて比較します。"

    @staticmethod
    def _detour_line(user_text: str) -> str:
        if "本題" in user_text or "戻" in user_text:
            return "寄り道の内容は補助情報として残しつつ、ここでは元の話題へ重心を戻します。"
        return "この寄り道は別の話題として保持し、元の話題を失わないようにします。"

    @staticmethod
    def _long_line() -> str:
        return "必要なら結論だけで切らず、理由・具体例・例外・まとめまで段階的につなげます。"

    @staticmethod
    def _smalltalk_line() -> str:
        return "雑談では無理に結論へ急がず、直前の話を拾いながら自然に話題を広げます。"

    def apply(self, user_text: str, base_reply: str, result: dict, chat) -> tuple[str, list[dict]]:
        active = self.score(user_text, chat)
        if not active:
            return base_reply, []

        additions = []
        names = [x["name"] for x in active]

        # Highest-value behavioral transformations first.
        if "conversation_repair" in names:
            additions.append(self._repair_line(user_text))

        if "context_followup" in names and "conversation_repair" not in names:
            x = self._context_line(user_text, chat)
            if x:
                additions.append(x)

        if "constraint_aware" in names:
            additions.append(self._constraint_line(user_text))

        if "uncertainty" in names:
            additions.append(self._uncertainty_line())

        if "disagreement" in names:
            additions.append(self._disagreement_line())

        if "detour_return" in names:
            additions.append(self._detour_line(user_text))

        if "long_form" in names:
            additions.append(self._long_line())

        if "smalltalk" in names and len(additions) < 2:
            additions.append(self._smalltalk_line())

        if "rich_explanation" in names and len(additions) < 2:
            additions.append(
                "説明では答えだけで終わらせず、判断理由と具体的な使い方までつなげます。"
            )

        # De-duplicate against the V53 reply and each other.
        final_additions = []
        for a in additions:
            if not a:
                continue
            if a in base_reply:
                continue
            if any(similarity(a, x) > 0.82 for x in final_additions):
                continue
            final_additions.append(a)

        if not final_additions:
            return base_reply, active

        # Preserve V53's answer as primary; circuits refine behavior.
        reply = base_reply.rstrip() + "\n\n" + "\n\n".join(final_additions[:3])
        return reply, active

    def stats(self) -> dict:
        return {
            "source_records": int(self.report.get("source_records", 0)),
            "source_categories": int(self.report.get("source_categories", 0)),
            "runtime_circuits": len(self.circuits),
            "runtime_dataset_required": False,
            "embedded_json_bytes": len(
                json.dumps(
                    {"circuits": self.circuits, "report": self.report},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
        }


class FAPV54(FAPV53):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.distilled_chat = DistilledConversationOrgan()

    def chat_once(self, user_text: str) -> dict:
        result = super().chat_once(user_text)
        old_reply = result.get("reply", "")

        distilled_reply, active = self.distilled_chat.apply(
            user_text=user_text,
            base_reply=old_reply,
            result=result,
            chat=self.chat,
        )

        if distilled_reply != old_reply:
            # V53 may already be speaking old_reply. Replace it with V54 final form.
            self.speech.stop()
            result["reply"] = distilled_reply
            result["voice"] = self.speech.speak(distilled_reply)

            if self.chat.turns and self.chat.turns[-1].role == "assistant":
                self.chat.turns[-1].text = distilled_reply
            self.chat.remember_reply(distilled_reply)

        result["version"] = "V54"
        result["distilled_circuits"] = active
        result["distillation"] = self.distilled_chat.stats()
        return result


def main_v54():
    fap = FAPV54()
    print("FAP V54 DISTILLED CONVERSATION")
    print("5,000 conversation examples -> 10 embedded behavior circuits")
    print("runtime dataset: NOT REQUIRED")
    print(
        "commands: :distillstat | :circuits | :brief | :normal | "
        ":rich | :verbose | :listen | :voice on|off | :stop | :quit"
    )

    while True:
        try:
            q = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            fap.speech.stop()
            print()
            break

        if not q:
            continue

        if q in (":q", ":quit", "exit", "quit"):
            fap.speech.stop()
            break

        if q == ":distillstat":
            print(json.dumps(fap.distilled_chat.stats(), ensure_ascii=False, indent=2))
            continue

        if q == ":circuits":
            print(json.dumps(
                {
                    k: {
                        "priority": v.get("priority"),
                        "detect": v.get("detect", [])[:8],
                        "plan": v.get("plan", []),
                        "target_chars": v.get("target_chars"),
                    }
                    for k, v in fap.distilled_chat.circuits.items()
                },
                ensure_ascii=False,
                indent=2,
            ))
            continue

        if q in (":brief", ":normal", ":rich", ":verbose"):
            mode = q[1:]
            fap.natural_chat.set_mode(mode)
            print("FAP> chat style=" + mode)
            continue

        if q == ":listen":
            print("FAP> listening...")
            heard = fap.speech_input.listen_once()
            if not heard.get("heard"):
                print("FAP[input]> " + str(heard.get("status")))
                continue
            print("You[voice]> " + heard["text"])
            result = fap.chat_once(heard["text"])
            print("FAP> " + result["reply"])
            continue

        if q == ":voice on":
            fap.speech.set_enabled(True)
            print("FAP> voice=on")
            continue

        if q == ":voice off":
            fap.speech.set_enabled(False)
            print("FAP> voice=off")
            continue

        if q == ":stop":
            fap.speech.stop()
            print("FAP> speech stopped")
            continue

        result = fap.chat_once(q)
        print("FAP> " + result["reply"])
        if result["distilled_circuits"]:
            print(
                "FAP[circuits]> "
                + ", ".join(x["name"] for x in result["distilled_circuits"])
            )


if __name__ == "__main__":
    main_v54()
