from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

SOURCE_RELEASE = "v78"
SOURCE_ARTIFACT_SHA256 = "e12f51a37681d3aabb4dd00d320fe1bf31362a7e939e454b4e7abc1f7db66909"
SOURCE_SELFTEST = "PASS"
SOURCE_COUNTS = {"circuits": 10, "memory_items": 22, "concept_nodes": 28, "concept_edges": 27}

# Ported from FAP V78 Gemma 4 Direct-Learning Integration.
# This is state/circuit distillation, not neural-weight transfer.
CIRCUITS: dict[str, dict] = {
    "uncertainty": {
        "priority": 0.825,
        "detect": ["確定事実", "仮説", "未確認情報", "区別", "検証", "混同", "分離"],
        "plan": ["入力文を要素に分割", "確定/仮説/未確認に分類", "根拠を確認", "不足情報を特定", "不確実性を明示"],
        "principles": ["確定事実と仮説を分離", "情報源の有無を明示", "確信度を過大評価しない"],
    },
    "conversation_repair": {
        "priority": 0.93,
        "detect": ["訂正", "修正", "違う", "ではない", "じゃなく", "前提", "解釈", "確認"],
        "plan": ["訂正を受領", "古い解釈を弱化", "新しい前提を抽出", "新しい前提へ切替", "必要なら確認"],
        "principles": ["古い解釈を固定しない", "新しい情報へ重み付け", "前提変更を明示"],
    },
    "constraint_aware": {
        "priority": 0.938,
        "detect": ["RAM", "メモリ", "速度", "精度", "安全", "制約", "条件", "容量", "圧縮"],
        "plan": ["制約を抽出", "核となる操作を最小化", "制約違反を確認", "冗長性を除去", "実行可能な形へ変換"],
        "principles": ["制約優先", "最小単位", "条件付き実行を明示", "再利用可能にする"],
    },
    "decomposition": {
        "priority": 0.938,
        "detect": ["分解", "サブゴール", "段階", "手順", "タスク", "検証可能", "再利用"],
        "plan": ["依頼を分析", "最小単位へ分割", "検証可能なステップ化", "依存関係を整理", "完了条件を置く"],
        "principles": ["原子性", "検証可能性", "冗長性排除", "再利用性"],
    },
    "verification": {
        "priority": 0.825,
        "detect": ["根拠", "反例", "矛盾", "未確認", "検証", "証拠"],
        "plan": ["主張を抽出", "根拠を確認", "反例を探す", "矛盾を検出", "未確認点を明示"],
        "principles": ["証拠要求", "反証可能性", "不確実性明示"],
    },
    "planning": {
        "priority": 0.825,
        "detect": ["完了条件", "途中失敗", "逆算", "再計画", "状態確認", "計画", "終わるまで"],
        "plan": ["目標を定義", "最終状態から逆算", "現在状態を評価", "ギャップを特定", "次の一手を選択", "結果で再計画"],
        "principles": ["状態遷移を明示", "失敗時は前提を再検証", "目標を保持"],
    },
    "debugging": {
        "priority": 0.945,
        "detect": ["エラー", "例外", "失敗", "不具合", "動か", "デバッグ", "再現性", "切り分け", "失敗点"],
        "plan": ["最小再現を作る", "変数を絞る", "原因仮説を1つ置く", "単一変更で検証", "結果を評価", "必要なら仮説を更新"],
        "principles": ["単一変更", "反証可能性", "確定事実を保持", "手順を再利用可能にする"],
    },
    "context_followup": {
        "priority": 0.925,
        "detect": ["それ", "これ", "その", "前の", "続き", "さっき", "どうなった", "結論", "要するに"],
        "plan": ["直近文脈の主題を特定", "参照対象を解決", "関連情報を抽出", "前後関係を確認", "結論か次の行動を返す"],
        "principles": ["文脈依存性を優先", "曖昧性を解消", "事実と推論を分離"],
    },
    "tool_use": {
        "priority": 0.938,
        "detect": ["ツール", "外部", "実行", "フォールバック", "API", "コマンド"],
        "plan": ["入力を識別", "適切なツールを選択", "実行", "結果を検証", "失敗時に代替手段", "結果を統合"],
        "principles": ["入力→ツール対応", "実行→検証", "失敗→代替", "最小情報保持"],
    },
    "long_form": {
        "priority": 0.825,
        "detect": ["詳しく", "長め", "結論", "理由", "具体例", "例外", "要約", "定義", "比較"],
        "plan": ["構造要素を抽出", "結論/理由/例/例外を分類", "関係を整理", "冗長性を圧縮", "構造化して返す"],
        "principles": ["事実優先", "結論→理由→例", "確定情報と推論を分離"],
    },
}

TEACHER_SHADOW = [
    "確定事実の定義：検証済みの情報。",
    "仮説の定義：検証が必要な推論。",
    "未確認情報の定義：情報源や検証プロセスが欠落している状態。",
    "混同の検出：同一情報が異なるカテゴリに分類されている場合、関係性を指摘する。",
    "訂正は前提変更のトリガー",
    "古い解釈は暫定",
    "入力の構造分解",
    "核となる操作手順の抽出",
    "事実と仮説の分離",
    "制約違反チェック機構の組み込み",
    "複雑な依頼を検証可能な小さなサブゴールに分割する。",
    "情報分類の基本構造（確定/仮説/未確認）",
    "検証の核は『根拠の妥当性評価』と『矛盾の特定』である。",
    "目標達成のため、逆順に分解する。",
    "失敗時、直前のステップの前提条件を再検証する。",
    "確定事実と仮説を明確に区別する。",
    "デバッグは、原因を特定するために、最小の変更で状態を操作し、結果を観察するプロセスである。",
    "代名詞は直前の文脈の主要実体を指す",
    "『続き』は未完了のプロセスや議論の継続を要求する",
    "ツール使用の基本フロー（入力→実行→検証→失敗処理）",
    "長文の構造は、結論→根拠（理由）→具体例/反例（例外）→まとめ（要約）の順序で構成される。",
    "再利用可能な手順は、説明の各セクションを「主張」「証拠」「境界条件」の3要素に分解すること。",
]

STRUCTURAL = {
    "conversation_repair": re.compile(r"(違う|ではなく|じゃなく|訂正|修正|というより)"),
    "uncertainty": re.compile(r"(不明|不確実|仮説|未確認|分から|可能性|断定)"),
    "constraint_aware": re.compile(r"(RAM|メモリ|速度|精度|安全|制約|条件|容量)", re.I),
    "decomposition": re.compile(r"(分解|サブゴール|段階|手順|タスク)"),
    "verification": re.compile(r"(検証|根拠|反例|矛盾|証拠)"),
    "planning": re.compile(r"(完了条件|逆算|再計画|途中失敗|計画|終わるまで)"),
    "debugging": re.compile(r"(エラー|例外|失敗|不具合|動か|修正|デバッグ)"),
    "context_followup": re.compile(r"(それ|これ|その|前の|続き|さっき|どうなった)"),
    "tool_use": re.compile(r"(ツール|外部|実行|フォールバック|API|コマンド)", re.I),
    "long_form": re.compile(r"(詳しく|長め|結論|理由|具体例|例外|要約|比較)"),
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_+\-]+|[一-龥ぁ-んァ-ンー]{2,}", (text or "").lower()))


@dataclass(frozen=True)
class Activation:
    name: str
    score: float
    hits: tuple[str, ...]


class DistilledFAPOrgan:
    """Local, dependency-free FAP responder using the V78 distilled state.

    This organ intentionally does not pretend to be Gemma 4. It provides local
    conversational primitives plus the distilled procedural circuits. Unknown
    factual questions are not fabricated.
    """

    def status(self) -> dict:
        return {
            "source_release": SOURCE_RELEASE,
            "source_selftest": SOURCE_SELFTEST,
            "source_artifact_sha256": SOURCE_ARTIFACT_SHA256,
            **SOURCE_COUNTS,
        }

    def activate(self, text: str, context: str = "", limit: int = 3) -> list[Activation]:
        t = str(text or "").strip()
        if not t:
            return []
        normalized = _norm(t)
        scored: list[Activation] = []
        for name, spec in CIRCUITS.items():
            score = 0.0
            hits: list[str] = []
            for cue in spec["detect"]:
                if _norm(cue) and _norm(cue) in normalized:
                    score += 1.0
                    hits.append(cue)
            pat = STRUCTURAL.get(name)
            if pat and pat.search(t):
                score += 2.0
            if name == "context_followup" and context.strip() and pat and pat.search(t):
                score += 1.0
            # Goal-aware arbitration: when the request explicitly keeps a goal to completion,
            # planning is primary while debugging may remain a secondary circuit.
            if name == "planning" and re.search(r"(目的|目標).*(達成|完了|終わる|最後まで)|(?:達成|完了|終わる|最後まで).*(目的|目標)", t):
                score += 4.0
            if name == "debugging" and re.search(r"(目的|目標).*(達成|完了|終わる|最後まで)|(?:達成|完了|終わる|最後まで).*(目的|目標)", t):
                score *= 0.72
            score *= float(spec.get("priority", 1.0))
            if score > 0:
                scored.append(Activation(name, round(score, 4), tuple(hits[:8])))
        scored.sort(key=lambda a: (-a.score, a.name))
        return scored[:max(1, int(limit))]

    def retrieve_shadow(self, text: str, context: str = "", limit: int = 2) -> list[str]:
        query = _tokens(text + " " + context[-1500:])
        if not query:
            return []
        ranked: list[tuple[float, str]] = []
        for item in TEACHER_SHADOW:
            tok = _tokens(item)
            if not tok:
                continue
            overlap = len(query & tok) / max(1, len(query | tok))
            if overlap > 0:
                ranked.append((overlap, item))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        return [x[1] for x in ranked[:limit]]

    @staticmethod
    def _history_context(history: list[Mapping]) -> str:
        rows = []
        for x in history[-8:]:
            role = x.get("role", "")
            text = str(x.get("text", "")).strip()
            if role in {"user", "assistant"} and text:
                rows.append(f"{role}: {text}")
        return "\n".join(rows)

    @staticmethod
    def _last_user(history: list[Mapping]) -> str:
        for x in reversed(history):
            if x.get("role") == "user" and str(x.get("text", "")).strip():
                return str(x["text"]).strip()
        return ""

    def _primitive_reply(self, text: str, history: list[Mapping]) -> str | None:
        t = text.strip()
        if re.search(r"^(こんにちは|こんばんは|おはよう|やあ|hello|hi)[。！!？?\s]*$", t, re.I):
            return "こんにちは。FAPです。今はPixel上のローカル蒸留回路で応答しています。何を確認しますか？"
        if re.search(r"(ありがとう|助かった|サンキュー|thanks?)", t, re.I):
            return "どういたしまして。続きがあれば、そのまま指示してください。"
        if re.search(r"(あなたは誰|何者|自己紹介|ファップとは|FAPとは)", t, re.I):
            return "私はFAPです。V78で蒸留した行動回路とteacher-shadow、会話記憶、専用器官を組み合わせてローカルに判断します。Gemma4:E2Bは必須ではありません。"
        if re.search(r"(何ができる|できること|能力|機能)", t):
            return "今のローカルFAPは、会話文脈、日時、計算、記憶、検証、天気ルーティング、画像ルーティングに加え、V78の10個の蒸留行動回路で訂正・制約・分解・検証・計画・デバッグ・文脈追跡・ツール選択などを処理できます。"
        if re.search(r"(元気|調子どう)", t):
            return "稼働中です。ローカル蒸留回路は利用できます。外部教師モデルには依存していません。"
        if re.search(r"(さっき|前に|前の|それ|これ|その).*(言|話|内容|何)", t):
            last = self._last_user(history)
            if last:
                return f"直前のユーザー発言として「{last}」を保持しています。"
        return None

    def run(self, text: str, history: list[Mapping]) -> dict:
        context = self._history_context(history)
        primitive = self._primitive_reply(text, history)
        if primitive is not None:
            return {
                "ok": True,
                "reply": primitive,
                "confidence": 0.91,
                "local": True,
                "needs_teacher": False,
                "active_circuits": [],
            }

        activations = self.activate(text, context)
        if activations:
            top = activations[0].name
            spec = CIRCUITS[top]
            plans = spec["plan"][:4]
            principles = spec["principles"][:2]
            shadow = self.retrieve_shadow(text, context, 1)
            lead = {
                "conversation_repair": "訂正として扱います。古い解釈を固定せず、新しい前提へ切り替えます。",
                "uncertainty": "確定事項と未確認事項を分けて扱います。",
                "constraint_aware": "制約を先に固定して、その範囲で実行可能な形へ落とします。",
                "decomposition": "依頼を検証可能な小さな段階へ分けます。",
                "verification": "主張・根拠・反例・未確認点の順で検証します。",
                "planning": "目標を保持し、現在状態との差から次の一手を決めます。",
                "debugging": "まず最小再現と失敗点の切り分けから進めます。",
                "context_followup": "直近の文脈を参照して続きとして処理します。",
                "tool_use": "入力に合う実行手段を選び、結果を検証して失敗時は代替へ切り替えます。",
                "long_form": "結論・理由・具体例・例外の順に構造化します。",
            }.get(top, "蒸留回路に基づいて処理します。")
            reply = lead + "\n処理: " + " → ".join(plans)
            if principles:
                reply += "\n原則: " + " / ".join(principles)
            if shadow:
                reply += "\nTeacher shadow（未検証）: " + shadow[0]
            return {
                "ok": True,
                "reply": reply,
                "confidence": min(0.94, 0.72 + activations[0].score / 10.0),
                "local": True,
                "needs_teacher": False,
                "active_circuits": [a.name for a in activations],
            }

        return {
            "ok": True,
            "reply": "その内容は現在の蒸留回路だけでは確定回答できません。分からない内容を作らず、必要なら質問を分解・検証・計画の形にして続けます。",
            "confidence": 0.56,
            "local": True,
            "needs_teacher": True,
            "active_circuits": [],
        }
