#!/usr/bin/env python3
from __future__ import annotations

import ast
import base64
import datetime as dt
import json
import math
import os
import re
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from fap_v78_distilled import DistilledFAPOrgan
from fap_spec_builder import SpecificationCompilerBuilder, BuilderError
from fap_code_generator import CodeGenerationError
from fap_program_synth import ProgramSynthesizer
from fap_factual_qa import FactualQAOrgan
from fap_reflective_conversation import ReflectiveConversationOrgan
from fap_inquiry_engine import InquiryEngine
from fap_scientific_modeling import ScientificModelComposer
from fap_hypothesis_engine import HypothesisEngine
from fap_research_frontier_chat import ResearchFrontierOrgan
from fap_research_cycle_chat import ResearchCycleOrgan
from fap_image_orchestrator import ImageOrchestrator

ROOT = Path(__file__).resolve().parent
WEB_FILE = ROOT / "web" / "FAP_Chat.html"
RUNTIME = ROOT / "runtime" / "v87_10"
SESSIONS = RUNTIME / "sessions"
ARTIFACTS = RUNTIME / "artifacts"
EVAL_LOG = RUNTIME / "fap_eval.jsonl"
for p in (RUNTIME, SESSIONS, ARTIFACTS):
    p.mkdir(parents=True, exist_ok=True)

VERSION = "87.10-program-synth"
HOST = os.environ.get("FAP_HOST", "127.0.0.1")
PORT = int(os.environ.get("FAP_PORT", "11439"))
OLLAMA_BASE = os.environ.get("FAP_OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("FAP_MODEL", "gemma4:e2b")
IMAGE_BASE = os.environ.get("FAP_IMAGE_API", "http://127.0.0.1:7860").rstrip("/")
DEFAULT_LOCATION = os.environ.get("FAP_DEFAULT_LOCATION", "").strip()
MAX_HISTORY = 24
TEACHER_FALLBACK = os.environ.get("FAP_TEACHER_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "on"}


def http_json(url: str, method: str = "GET", data: dict | None = None, timeout: float = 12.0) -> Any:
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "FAP-V87.10/1.0")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def compact(text: str, n: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def safe_session(value: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]", "_", str(value or "default"))[:80]
    return s or "default"


class SessionMemory:
    """Bounded session memory with a hot in-process cache.

    The old implementation re-read and rewrote the complete JSON history for
    every single message. A normal turn therefore did two full read/modify/write
    cycles, and latency grew with conversation length. Keep the same on-disk
    format, but cache the bounded history and allow a whole turn to be committed
    with one write.
    """

    def __init__(self):
        self._cache: dict[str, list[dict]] = {}

    def path(self, sid: str) -> Path:
        return SESSIONS / f"{safe_session(sid)}.json"

    def _key(self, sid: str) -> str:
        return safe_session(sid)

    def load(self, sid: str) -> list[dict]:
        key = self._key(sid)
        cached = self._cache.get(key)
        if cached is not None:
            return list(cached[-MAX_HISTORY:])

        p = self.path(sid)
        if not p.exists():
            self._cache[key] = []
            return []
        try:
            rows = json.loads(p.read_text(encoding="utf-8"))
            rows = rows[-MAX_HISTORY:] if isinstance(rows, list) else []
        except Exception:
            rows = []
        self._cache[key] = list(rows)
        return list(rows)

    def append_many(self, sid: str, rows_to_add) -> None:
        rows = self.load(sid)
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        for item in rows_to_add:
            role, text, meta = item
            rows.append({
                "role": str(role),
                "text": str(text),
                "meta": meta or {},
                "ts": now,
            })
        rows = rows[-MAX_HISTORY:]
        self._cache[self._key(sid)] = list(rows)
        # Compact JSON materially reduces bytes written on Windows while
        # retaining exact compatibility with existing session files.
        self.path(sid).write_text(
            json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    def append(self, sid: str, role: str, text: str, meta: dict | None = None) -> None:
        self.append_many(sid, ((role, text, meta or {}),))

    def append_exchange(
        self,
        sid: str,
        user_text: str,
        assistant_text: str,
        user_meta: dict | None = None,
        assistant_meta: dict | None = None,
    ) -> None:
        self.append_many(
            sid,
            (
                ("user", user_text, user_meta or {}),
                ("assistant", assistant_text, assistant_meta or {}),
            ),
        )


MEMORY = SessionMemory()


@dataclass
class Intent:
    name: str
    confidence: float
    candidates: list[tuple[str, float]]


class IntentOrgan:
    def classify(self, text: str) -> Intent:
        t = text.strip().lower()
        scores = {
            "weather": 0.02,
            "datetime": 0.02,
            "calculator": 0.02,
            "image_generate": 0.02,
            "image_capability": 0.02,
            "memory": 0.02,
            "builder": 0.02,
            "chat": 0.18,
        }

        if re.search(r"(天気|気温|降水|雨|雪|晴|曇|weather|temperature)", t):
            scores["weather"] += 0.90
        if re.search(r"(何日|何時|曜日|日付|時刻|datetime|date|time)", t):
            scores["datetime"] += 0.88
        if re.search(r"(計算|いくら|何%|何％|\d\s*[+\-*/×÷^]\s*\d)", t):
            scores["calculator"] += 0.82

        image_word = bool(re.search(r"(画像|写真|イラスト|絵|image|photo|picture)", t))
        gen_word = bool(re.search(r"(生成|作って|描いて|render|generate|create)", t))
        can_word = bool(re.search(r"(できますか|できる[？?]?|可能|使えますか|対応)", t))
        if image_word and gen_word and can_word:
            scores["image_capability"] += 1.02
        elif image_word and gen_word:
            scores["image_generate"] += 0.98
        elif image_word and can_word:
            scores["image_capability"] += 0.88

        if re.search(r"(覚えて|記憶|前に言った|さっき|以前の会話|memory)", t):
            scores["memory"] += 0.76

        # V87.05: creation intent stays inside Builder even for an unknown target.
        # Image creation remains owned by ImageOrgan.
        build_verb = bool(re.search(r"(作って|作成(?:して|できますか|できる)?|生成(?:して)?|構築(?:して)?|build|create|make)", t, re.I))
        if build_verb and not image_word:
            scores["builder"] += 1.12

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best, score = ranked[0]
        second = ranked[1][1]
        confidence = min(0.99, max(0.35, score - max(0.0, second - 0.20)))
        return Intent(best, round(confidence, 3), [(k, round(v, 3)) for k, v in ranked[:4]])


class CalculatorOrgan:
    ALLOWED = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
        ast.USub: lambda a: -a,
        ast.UAdd: lambda a: +a,
    }

    def extract(self, text: str) -> str | None:
        s = text.replace("×", "*").replace("÷", "/").replace("＾", "^").replace("^", "**")
        candidates = re.findall(r"[0-9][0-9\.\s+\-*/()%]*", s)
        candidates = [re.sub(r"\s+$", "", x).strip() for x in candidates if x.strip()]
        if not candidates:
            return None
        # Prefer the longest arithmetic-looking span so `12+34はいくら` stays `12+34`.
        candidates.sort(key=lambda x: (bool(re.search(r"[+\-*/%()]", x[1:])), len(x)), reverse=True)
        return candidates[0]

    def eval_node(self, node):
        if isinstance(node, ast.Expression):
            return self.eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in self.ALLOWED:
            return self.ALLOWED[type(node.op)](self.eval_node(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in self.ALLOWED:
            a, b = self.eval_node(node.left), self.eval_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(b) > 12:
                raise ValueError("exponent too large")
            value = self.ALLOWED[type(node.op)](a, b)
            if not math.isfinite(float(value)) or abs(float(value)) > 1e18:
                raise ValueError("result out of range")
            return value
        raise ValueError("unsupported expression")

    def run(self, text: str) -> dict:
        expr = self.extract(text)
        if not expr:
            return {"ok": False, "reply": "計算式を特定できませんでした。"}
        try:
            tree = ast.parse(expr, mode="eval")
            value = self.eval_node(tree)
            return {"ok": True, "reply": f"{expr} = {value}", "confidence": 0.99}
        except Exception as e:
            return {"ok": False, "reply": f"計算式を安全に評価できませんでした: {e}"}


class DateTimeOrgan:
    def run(self, text: str) -> dict:
        now = dt.datetime.now().astimezone()
        weekdays = "月火水木金土日"
        if re.search(r"(何時|時刻|time)", text, re.I):
            reply = now.strftime("%Y年%m月%d日 ") + f"({weekdays[now.weekday()]}) " + now.strftime("%H:%M:%S %Z")
        else:
            reply = now.strftime("%Y年%m月%d日") + f"（{weekdays[now.weekday()]}曜日）です。"
        return {"ok": True, "reply": reply, "confidence": 0.99}


class WeatherOrgan:
    LOCATION_PATTERNS = [
        re.compile(r"(.{1,24}?)(?:の|で)(?:今日|明日|現在)?の?(?:天気|気温|降水)"),
        re.compile(r"(?:天気|気温|降水).*?(?:は|@)\s*(.{1,24})"),
    ]

    def location_from(self, text: str) -> str:
        for pat in self.LOCATION_PATTERNS:
            m = pat.search(text)
            if m:
                loc = m.group(1).strip(" 、。?？")
                loc = re.sub(r"^(今日|明日|現在|きょう|あした)", "", loc).strip()
                if loc in {"今日","明日","現在","きょう","あした","今","本日"}:
                    loc = ""
                if loc:
                    return loc
        return DEFAULT_LOCATION

    def run(self, text: str) -> dict:
        loc = self.location_from(text)
        if not loc:
            return {
                "ok": False,
                "reply": "天気の質問だと判断しました。地域を指定してください。例: 「米子市の今日の天気は？」",
                "confidence": 0.93,
            }
        try:
            q = urllib.parse.urlencode({"name": loc, "count": 1, "language": "ja", "format": "json"})
            geo = http_json("https://geocoding-api.open-meteo.com/v1/search?" + q, timeout=8)
            rows = geo.get("results") or []
            if not rows:
                return {"ok": False, "reply": f"「{loc}」の地点を特定できませんでした。", "confidence": 0.90}
            g = rows[0]
            params = urllib.parse.urlencode({
                "latitude": g["latitude"],
                "longitude": g["longitude"],
                "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                "timezone": "auto",
            })
            wx = http_json("https://api.open-meteo.com/v1/forecast?" + params, timeout=8)
            c = wx.get("current") or {}
            place = " ".join(x for x in [g.get("name"), g.get("admin1")] if x)
            reply = (
                f"{place}の現在の天気です。\n"
                f"気温 {c.get('temperature_2m','?')}℃ / 体感 {c.get('apparent_temperature','?')}℃\n"
                f"降水 {c.get('precipitation','?')} mm / 風速 {c.get('wind_speed_10m','?')} km/h\n"
                f"weather code: {c.get('weather_code','?')}"
            )
            return {"ok": True, "reply": reply, "confidence": 0.96}
        except Exception as e:
            return {"ok": False, "reply": f"天気器官は選択できましたが、天気取得に失敗しました: {compact(e)}", "confidence": 0.88}


class ImageOrgan:
    def __init__(self):
        self.orchestrator = ImageOrchestrator(
            image_base=IMAGE_BASE,
            artifact_dir=ARTIFACTS,
            http_json=http_json,
        )

    def available(self) -> tuple[bool, str]:
        return self.orchestrator.available()

    def prompt_from(self, text: str) -> str:
        # Backward-compatible helper retained for callers/tests that inspect the
        # old ImageOrgan surface. V87.56 generation itself uses ImageRequestSpec.
        p = re.sub(r"(画像|写真|イラスト|絵).{0,8}(生成|作って|描いて)", "", text)
        p = re.sub(r"(生成して|作って|描いて|ください|お願い)", "", p).strip(" 、。")
        return p or text.strip()

    def run_capability(self) -> dict:
        ok, reply = self.available()
        if ok:
            reply += (
                " 要求を構造化し、複数候補を生成して、利用可能なら"
                "CLIP interrogateで実画像を検査し、不足要素を再生成します。"
            )
        return {
            "ok": ok,
            "reply": reply,
            "confidence": 0.99 if ok else 0.96,
            "image_orchestrator": "87.56",
        }

    def run_generate(self, text: str) -> dict:
        return self.orchestrator.generate(text)


class E2BOrgan:
    def available(self) -> bool:
        try:
            data = http_json(OLLAMA_BASE + "/api/tags", timeout=3)
            names = [str(x.get("name", "")) for x in data.get("models", [])]
            return any(n == OLLAMA_MODEL or n.startswith(OLLAMA_MODEL + ":") or n.startswith(OLLAMA_MODEL) for n in names)
        except Exception:
            return False

    def run(self, text: str, history: list[dict]) -> dict:
        if not self.available():
            return {
                "ok": False,
                "reply": "一般会話・自由推論にはGemma4:E2B Coreが必要ですが、現在は接続できません。",
                "confidence": 0.72,
            }
        recent = [{"role": x["role"], "content": x["text"]} for x in history[-12:] if x.get("role") in ("user", "assistant")]
        system = (
            "あなたはFAP V87.02のReasoning Organ。FAPとして日本語で直接回答する。"
            "入力意図に合う回答を優先し、できない能力をできると主張しない。"
            "日時・天気・画像など専用器官の結果を捏造しない。Qwenは使用しない。"
        )
        messages = [{"role": "system", "content": system}] + recent + [{"role": "user", "content": text}]
        try:
            out = http_json(
                OLLAMA_BASE + "/api/chat",
                method="POST",
                data={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
                timeout=120,
            )
            reply = ((out.get("message") or {}).get("content") or "").strip()
            if not reply:
                raise RuntimeError("empty model reply")
            return {"ok": True, "reply": reply, "confidence": 0.88}
        except Exception as e:
            return {"ok": False, "reply": f"Gemma4:E2B推論に失敗しました: {compact(e)}", "confidence": 0.65}


class MemoryOrgan:
    def run(self, text: str, history: list[dict]) -> dict:
        if not history:
            return {"ok": True, "reply": "このセッションにはまだ参照できる会話記憶がありません。", "confidence": 0.95}
        user_rows = [x["text"] for x in history if x.get("role") == "user"]
        if not user_rows:
            return {"ok": True, "reply": "ユーザー発言の記憶はまだありません。", "confidence": 0.95}
        tail = user_rows[-6:]
        return {"ok": True, "reply": "直近のユーザー発言を保持しています:\n- " + "\n- ".join(map(compact, tail)), "confidence": 0.94}


class VerificationOrgan:
    def verify(self, intent: Intent, result: dict) -> tuple[str, str]:
        reply = str(result.get("reply", ""))
        ok = bool(result.get("ok"))
        if not reply.strip():
            return "NG", "空の回答です。"
        if intent.name == "weather" and re.search(r"\d{4}年\d{2}月\d{2}日.*です。?$", reply) and "天気" not in reply:
            return "NG", "天気質問に日時だけを返しています。"
        if intent.name.startswith("image") and "文脈" in reply and "画像" not in reply:
            return "NG", "画像能力質問を文脈検索へ誤ルーティングしています。"
        if result.get("image_orchestrated"):
            if not result.get("ok"):
                return "PARTIAL", "画像オーケストレーターは起動しましたが、候補生成に成功していません。"
            if result.get("visual_verified") and float(result.get("image_score", 0.0)) >= 0.80:
                return "OK", "実画像をCLIP自己検査し、要求適合度の高い候補を選択しています。"
            if result.get("visual_verified"):
                return "PARTIAL", "画像は生成され実画像検査も行いましたが、要求適合度が目標値に届いていません。"
            return "PARTIAL", "画像生成は成功しましたが、実画像の意味検査器官が未接続のため視覚的一致は未検証です。"
        if result.get("recommendation_reasoning"):
            if not result.get("recommendation_verified"):
                return "PARTIAL", "推薦経路は起動しましたが、条件に合う候補を検証できません。"
            if not result.get("candidate_ids"):
                return "PARTIAL", "推薦結果は生成されましたが、候補トレースがありません。"
            return "OK", "推薦条件を文脈から合成し、ローカル候補を順位付けして回答しています。"
        if result.get("rule_reasoning"):
            if not result.get("rule_verified"):
                return "PARTIAL", "汎用ルール推論は起動しましたが、導出結果を検証できません。"
            if not result.get("evidence_ids"):
                return "PARTIAL", "ルール推論の結果は得られましたが、根拠トレースを追跡できません。"
            return "OK", "文脈から対象を解決し、汎用ルールを再帰適用して根拠トレース付きで回答しています。"
        if result.get("derivation_reasoning"):
            if not result.get("derivation_verified"):
                return "PARTIAL", "導出経路は起動しましたが、前提式から目標式への記号的含意を検証できません。"
            if not result.get("evidence_ids"):
                return "PARTIAL", "導出式は得られましたが、参照したローカル知識レコードを追跡できません。"
            return "OK", "ローカル知識を取得し、記号正規化・代数的含意検証・独立カウンターチェックを通過しています。"
        if result.get("factual_qa"):
            if not result.get("answer_coverage"):
                return "NG", "事実質問を検出しましたが、直接回答がありません。"
            return "OK", "事実質問に対してローカル知識から直接回答しています。"
        if result.get("scientific_model"):
            if not result.get("model_id"):
                return "PARTIAL", "科学モデル説明は生成されましたが、参照モデルを特定できません。"
            return "OK", f"構造化科学モデル {result.get('model_id')} に基づいて説明しています。"
        if result.get("hypothesis_reasoning"):
            n = int(result.get("generated_hypotheses", 0))
            if n <= 0:
                return "PARTIAL", "仮説推論を選択しましたが、競合仮説を生成できませんでした。"
            return "OK", f"{n}件の競合仮説を生成し、予測・反証条件・次の観測を分離しました。仮説は検証済み事実へ自動昇格しません。"
        if result.get("research_cycle"):
            n = int(result.get("cycle_count", 0))
            return "OK", f"{n}件の研究サイクル候補から、仮説・反証条件・次の検証を提示しています。文献一致だけで事実へ昇格しません。"
        if result.get("research_frontier"):
            n = int(result.get("papers_processed", 0))
            return "OK", f"{n}件規模の文献スクリーニング由来フロンティアから未解決候補を提示しています。未記載を科学的未解決とは断定しません。"
        if result.get("inquiry_reasoning"):
            resolved = int(result.get("resolved_questions", 0))
            generated = int(result.get("generated_questions", 0))
            unresolved = int(result.get("unresolved_questions", 0))
            learning = result.get("epistemic_learning") or {}
            conflicts = int(learning.get("conflicts", 0))
            if conflicts:
                return "PARTIAL", f"自己質問 {resolved}/{generated} を解消しましたが、{conflicts}件の知識矛盾を隔離しました。"
            if result.get("needs_live_data"):
                return "PARTIAL", f"自己質問 {resolved}/{generated} を解消しましたが、確定には最新データが必要です。"
            if result.get("audit_mode") and unresolved:
                return "PARTIAL", f"自己質問 {resolved}/{generated} を根拠付きで解消し、{unresolved}件を未解決として保持しています。"
            return "OK", f"自己質問を価値順に処理し、{resolved}/{generated}件を根拠付きで解消して回答を構成しました。"
        if result.get("reflective_reasoning"):
            if result.get("needs_live_data"):
                return "PARTIAL", "仕組みは説明できますが、この質問の確定回答には最新の観測・予報データが必要です。"
            if not result.get("grounded") or not result.get("evidence_ids"):
                return "PARTIAL", "会話推論は動作しましたが、ローカル根拠へ接続できていません。"
            return "OK", "ローカル知識へ接続し、質問形式に合わせて説明を組み立てています。"
        if result.get("needs_teacher") or "確定回答できません" in reply or "分からない内容を作らず" in reply:
            return "PARTIAL", "ローカル経路だけでは質問への確定回答に到達していません。"
        if ok:
            return "OK", "意図と実行結果が一致しています。"
        return "PARTIAL", "意図は認識できていますが、外部能力または必要情報が不足しています。"


class FAPV8710:
    def __init__(self):
        self.intent = IntentOrgan()
        self.calc = CalculatorOrgan()
        self.datetime = DateTimeOrgan()
        self.weather = WeatherOrgan()
        self.image = ImageOrgan()
        self.distilled = DistilledFAPOrgan()
        self.builder = SpecificationCompilerBuilder(ARTIFACTS, RUNTIME / "workspace")
        self.codegen = ProgramSynthesizer(ARTIFACTS, RUNTIME / "code_workspace")
        self.e2b = E2BOrgan()
        self.memory = MemoryOrgan()
        self.factual = FactualQAOrgan()
        self.inquiry = InquiryEngine(ROOT)
        self.scientific_model = ScientificModelComposer(ROOT)
        self.hypothesis = HypothesisEngine(ROOT)
        self.research_frontier = ResearchFrontierOrgan(ROOT)
        self.research_cycle = ResearchCycleOrgan(ROOT)
        self.reflective = ReflectiveConversationOrgan()
        self.verify = VerificationOrgan()
        self.lock = threading.Lock()

    def capabilities(self) -> list[str]:
        caps = [
            "intent", "datetime", "calculator", "memory", "verification", "fap-eval",
            "distilled-v78-local-chat", "behavior-circuits:10", "teacher-shadow:22",
            "builder-stage4", "builder:spec-compiler", "code-generator-stage3", "codegen:program-ir", "codegen:primitive-composition", "codegen:python", "codegen:html", "codegen:json", "codegen:markdown", "codegen:self-test", "codegen:repair-loop", "builder:constraint-extractor", "builder:generic-grid-composer", "builder:concept-resolver", "builder:mechanism-decomposition", "builder:generic-intent", "builder:composition", "builder:single-html", "builder:tetris", "builder:breakout", "builder:pong", "builder:snake", "builder:minesweeper", "builder:2048", "builder:memory-match", "builder:json",
            "weather", "image-routing", "local-factual-qa", "direct-fact-routing",
            "reflective-local-chat", "knowledge-grounded-conversation", "causal-explanation",
            "topic-followup-resolution", "generic-question-generation", "question-resolution-loop",
            "retrieval-grounded-inquiry", "data-driven-knowledge",
            "structured-scientific-models", "equation-grounded-explanation",
            "generic-hypothesis-generation", "falsification-first-reasoning",
            "competing-hypothesis-analysis", "provisional-hypothesis-memory",
            "research-frontier-chat", "literature-gap-clustering",
            "targeted-research-cycles", "literature-rechallenge-loop",
            "hypothesis-to-falsification-cycle",
            "image-orchestrator:v87.56", "image-request-spec",
            "multi-candidate-image-generation", "image-repair-loop",
            "optional-clip-image-self-critique",
        ]
        if self.image.available()[0]:
            caps.append("image-generation")
        if self.e2b.available():
            caps.append("optional-teacher:gemma4:e2b")
        return caps

    def chat_status(self) -> dict:
        # Chat responses only need a small liveness/version snapshot. The full
        # status tree probes optional local services and recursively assembles
        # capability metadata, which can add many seconds on Windows when those
        # services are absent or slow.
        return {
            "name": "FAP",
            "version": VERSION,
            "state": "ready",
            "builder": {"stage": 4, "local": True},
            "code_generator": {"stage": 3, "local": True},
            "protocol": "1.0",
        }

    def status(self) -> dict:
        teacher = self.e2b.available()
        return {
            "name": "FAP",
            "version": VERSION,
            "state": "ready",
            "model": "distilled:v78",
            "local_brain": True,
            "distillation": self.distilled.status(),
            "teacher_model": OLLAMA_MODEL,
            "teacher_available": teacher,
            "teacher_fallback": TEACHER_FALLBACK,
            "builder": {"stage": 4, "local": True, "mode": "natural-language-specification-compilation", "targets": ["compiled_grid_game", "tetris", "breakout", "pong", "snake", "minesweeper", "2048", "memory_match", "generic_page", "generic_config"]},
            "code_generator": {"stage": 3, "local": True, "mode": "natural-language-to-program-ir-to-code-verify-selftest-repair", "targets": ["python_calculator", "python_csv_stats", "python_composed", "python_program_ir", "html_notepad", "html_counter", "html_composed", "json_config", "markdown_document"]},
            "e2b": teacher,
            "capabilities": self.capabilities(),
            "protocol": "1.0",
        }

    def route(self, intent: Intent, text: str, history: list[dict]) -> dict:
        if intent.name == "weather":
            return self.weather.run(text)
        if intent.name == "datetime":
            return self.datetime.run(text)
        if intent.name == "calculator":
            return self.calc.run(text)
        if intent.name == "image_capability":
            return self.image.run_capability()
        if intent.name == "image_generate":
            return self.image.run_generate(text)
        if intent.name == "memory":
            return self.memory.run(text, history)
        if intent.name == "builder":
            if self.codegen.claims(text):
                try:
                    return self.codegen.build(text)
                except CodeGenerationError as e:
                    return {"ok": False, "reply": f"Code Generator Stage 3では完了できませんでした: {e}", "confidence": 0.86}
            try:
                return self.builder.build(text)
            except BuilderError as e:
                return {"ok": False, "reply": f"Builder Stage 4では完了できませんでした: {e}", "confidence": 0.86}

        # High-precision factual questions should be answered before procedural
        # distilled circuits. This prevents words such as "speed" from being
        # mistaken for a performance constraint.
        factual = self.factual.run(text)
        if factual is not None:
            return factual

        # Structured scientific models provide equation/mechanism explanations
        # without topic-specific chat branches. New coverage is added as data.
        scientific_model = self.scientific_model.run(text, history)
        if scientific_model is not None:
            return scientific_model

        # Abductive reasoning is triggered only for hypothesis/alternative/
        # falsification language, so ordinary science explanations keep using
        # the structured model path above.
        cycle = self.research_cycle.run(text, history)
        if cycle is not None:
            return cycle

        frontier = self.research_frontier.run(text, history)
        if frontier is not None:
            return frontier

        hypothesis = self.hypothesis.run(text, history)
        if hypothesis is not None:
            return hypothesis

        # Generic inquiry is data-driven: retrieve local evidence, generate
        # epistemic subquestions, try to resolve them, then synthesize. Topic
        # growth happens in knowledge data rather than chat-routing branches.
        inquiry = self.inquiry.run(text, history)
        if inquiry is not None:
            return inquiry

        # Broader local conversation still stays knowledge-grounded. The
        # reflective organ can explain mechanisms, causes, boundaries and
        # context follow-ups for topics it explicitly knows. Unknown topics fall
        # through rather than being fabricated.
        reflective = self.reflective.run(text, history)
        if reflective is not None:
            return reflective

        # General conversation is local-first. Gemma4:E2B is an optional teacher, not a dependency.
        local = self.distilled.run(text, history)
        if TEACHER_FALLBACK and local.get("needs_teacher") and self.e2b.available():
            teacher = self.e2b.run(text, history)
            if teacher.get("ok"):
                teacher["teacher_used"] = True
                teacher["local_distilled_first"] = True
                return teacher
        return local

    def chat(self, text: str, sid: str) -> dict:
        history = MEMORY.load(sid)
        intent = self.intent.classify(text)
        result = self.route(intent, text, history)
        verdict, critic = self.verify.verify(intent, result)

        route = ["intent", intent.name, "verify", "integrate"]
        reply = str(result.get("reply", "")).strip()
        confidence = min(float(result.get("confidence", intent.confidence)), intent.confidence if intent.name != "chat" else 0.99)

        MEMORY.append(sid, "user", text, {"intent": intent.name})
        MEMORY.append(sid, "assistant", reply, {"intent": intent.name, "verdict": verdict})

        event = {
            "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "session": safe_session(sid),
            "text": compact(text, 500),
            "intent": intent.name,
            "candidates": intent.candidates,
            "ok": bool(result.get("ok")),
            "verdict": verdict,
            "confidence": confidence,
        }
        with self.lock:
            with EVAL_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return {
            "reply": reply,
            "ability": intent.name,
            "confidence": round(confidence, 3),
            "route": route,
            "critic": f"査定: {verdict}\n{critic}",
            "verdict": verdict,
            "artifacts": result.get("artifacts", []),
            "intent_candidates": intent.candidates,
            "status": self.chat_status(),
        }


CORE = FAPV8710()


class Handler(SimpleHTTPRequestHandler):
    server_version = "FAPV87.10PS"

    def log_message(self, fmt: str, *args) -> None:
        print("[FAP WEB] " + (fmt % args))

    def cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def send_json(self, obj: Any, code: int = 200) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.cors_headers()
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors_headers()
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html", "/FAP_Chat.html"):
            if not WEB_FILE.exists():
                self.send_json({"error": "web/FAP_Chat.html not found"}, 404)
                return
            raw = WEB_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.cors_headers()
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/v1/status":
            self.send_json(CORE.status())
            return
        if path == "/api/v1/capabilities":
            self.send_json({"version": VERSION, "capabilities": CORE.capabilities()})
            return
        if path.startswith("/artifacts/"):
            name = Path(path).name
            file = ARTIFACTS / name
            if not file.exists() or file.parent != ARTIFACTS:
                self.send_json({"error": "artifact not found"}, 404)
                return
            raw = file.read_bytes()
            ctype = {
                ".html": "text/html; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".py": "text/x-python; charset=utf-8",
                ".txt": "text/plain; charset=utf-8",
                ".md": "text/markdown; charset=utf-8",
                ".png": "image/png",
            }.get(file.suffix.lower(), "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.cors_headers()
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/v1/chat":
            self.send_json({"error": "not found"}, 404)
            return
        try:
            size = min(int(self.headers.get("Content-Length", "0") or "0"), 1_000_000)
            data = json.loads(self.rfile.read(size).decode("utf-8")) if size else {}
            text = str(data.get("text", "")).strip()
            sid = safe_session(str(data.get("session", "default")))
            if not text:
                self.send_json({"error": "text is required"}, 400)
                return
            self.send_json(CORE.chat(text, sid))
        except Exception as e:
            self.send_json({"error": compact(e)}, 500)


def main() -> None:
    if not WEB_FILE.exists():
        raise SystemExit(f"missing UI: {WEB_FILE}")
    print(f"FAP V{VERSION} Distilled + Specification Compiler + Program Synthesizer Gateway")
    print(f"UI: http://{HOST}:{PORT}/")
    print("Local brain: V78 distilled circuits + teacher-shadow")
    print("Builder: V87.07 constraint extractor + specification compiler (Stage 4)")
    print("Code Generator: V87.10 natural language + Program IR + verified emitter + self-test + repair loop (Stage 3)")
    print(f"Optional teacher: {OLLAMA_MODEL} @ {OLLAMA_BASE} (fallback={TEACHER_FALLBACK})")
    print("Qwen: not used")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
