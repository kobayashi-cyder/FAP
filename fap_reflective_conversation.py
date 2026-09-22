from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Concept:
    concept_id: str
    aliases: tuple[str, ...]
    summary: str
    mechanisms: tuple[str, ...]
    boundaries: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    plain: str = ""


CONCEPTS: tuple[Concept, ...] = (
    Concept(
        "atmospheric_motion",
        ("大気の運動", "大気運動", "大気循環", "気流", "風の仕組み", "atmospheric motion", "atmospheric circulation"),
        "大気の運動は、空間的な気圧・密度・温度の差から生じる力と、地球の自転、重力、地表摩擦の組み合わせで決まります。",
        (
            "気圧傾度力が空気を高圧側から低圧側へ加速しようとします。",
            "地球の自転によるコリオリ効果が大規模な水平流を曲げ、上空では気圧傾度力との釣り合いに近い地衡風が基本になります。",
            "地表付近では摩擦が風速を落とすため釣り合いが崩れ、風は等圧線を横切って低圧側へ流れ込みやすくなります。",
            "鉛直方向では浮力、加熱・冷却、水蒸気の凝結、前線、地形などが上昇流・下降流を作ります。",
        ),
        (
            "支配的な力は空間・時間スケールで変わります。台風、ジェット気流、海陸風、積乱雲では同じ大気運動でも力のバランスが異なります。",
            "コリオリ効果は赤道付近や非常に小さいスケールでは弱く、局地的な流れでは摩擦や浮力が相対的に重要になります。",
        ),
        ("pressure_gradient", "coriolis", "convection"),
        "要するに、空気は場所ごとの気圧や温度の違いで動き始め、その流れを地球の自転や地面との摩擦が曲げたり弱めたりします。上昇・下降には浮力や加熱・冷却も効きます。",
    ),
    Concept(
        "pressure_gradient",
        ("気圧傾度力", "圧力傾度力", "pressure gradient force", "pressure gradient"),
        "気圧傾度力は、圧力が空間的に不均一なときに流体を高圧側から低圧側へ加速する力です。",
        (
            "圧力差そのものではなく、距離あたりの圧力変化が加速度を決めます。",
            "大気では水平気圧傾度が風を駆動し、鉛直方向では重力との釣り合いが静水圧平衡を作ります。",
        ),
        ("圧力傾度が強いほど、他の条件が同じなら加速も強くなります。",),
    ),
    Concept(
        "coriolis",
        ("コリオリ", "コリオリ力", "コリオリ効果", "coriolis", "coriolis force"),
        "コリオリ効果は、回転する地球上で運動を見ると現れる見かけの偏向です。",
        (
            "北半球では進行方向の右、南半球では左へ偏向する向きになります。",
            "速度が大きいほど、緯度が高いほど効果は強くなり、赤道では水平成分がゼロになります。",
            "大規模な大気・海洋運動では気圧傾度力との釣り合いを作り、流れを等圧線に沿わせる重要な役割を持ちます。",
        ),
        ("コリオリ効果そのものが流体へエネルギーを与えるわけではなく、主に運動方向を変えます。",),
    ),
    Concept(
        "convection",
        ("対流", "自然対流", "convection", "浮力"),
        "対流は、密度差と重力による浮力で流体が上下に動き、熱や物質を運ぶ現象です。",
        (
            "加熱された流体は一般に膨張して密度が下がり、周囲より軽くなると上昇しやすくなります。",
            "上昇した流体が冷却されると密度差が変わり、循環が形成されます。",
            "大気では水蒸気の凝結に伴う潜熱放出も浮力を強め、積乱雲などの発達に効きます。",
        ),
        ("安定成層では鉛直運動が抑えられ、不安定成層では対流が成長しやすくなります。",),
    ),
    Concept(
        "wave",
        ("波", "波動", "wave", "wave motion"),
        "波は、物質そのものが一方向へ運ばれ続けなくても、擾乱やエネルギーが空間を伝わる現象です。",
        (
            "多くの線形波では、復元力と慣性の組み合わせが振動と伝播を作ります。",
            "波長、周波数、位相速度の間には、単純な非分散波なら v=fλ の関係があります。",
        ),
        ("媒質や分散関係によって位相速度と群速度は異なることがあります。",),
    ),
    Concept(
        "energy",
        ("エネルギー", "energy", "エネルギー保存"),
        "エネルギーは、物理系の状態を記述する保存的な量で、運動・位置・熱・場など複数の形を取ります。",
        (
            "閉じた系では総エネルギーは保存され、形の間で変換されます。",
            "力学では仕事が運動エネルギーを変え、熱力学では熱と仕事が内部エネルギーの変化に関係します。",
        ),
        ("どのエネルギーを数えるかは系の境界とモデルに依存します。",),
    ),
    Concept(
        "entropy",
        ("エントロピー", "entropy", "熱力学第二法則"),
        "熱力学的エントロピーは、巨視的状態に対応する微視的状態数や、エネルギーの散らばり方を表す状態量です。",
        (
            "孤立系では自発過程によって総エントロピーは減少しない、というのが第二法則の基本的な表現です。",
            "局所的にエントロピーが下がることは可能ですが、その場合は周囲を含む全体で増加が補われます。",
        ),
        ("『無秩序さ』という比喩だけでは正確でない場合があり、統計力学では状態数との関係で扱う方が明確です。",),
    ),
    Concept(
        "natural_selection",
        ("自然選択", "進化", "natural selection", "evolution"),
        "自然選択は、遺伝する変異のうち繁殖成功に差を生むものが、世代を通じて集団中の頻度を変える過程です。",
        (
            "変異が存在し、その一部が遺伝し、環境のもとで生存・繁殖成功に差があると選択が働きます。",
            "変化する主体は世代をまたいだ集団の遺伝的構成で、個体が必要に応じて目的的に進化するわけではありません。",
        ),
        ("遺伝的浮動、遺伝子流動、突然変異など自然選択以外の過程も進化に寄与します。",),
    ),
    Concept(
        "dna_expression",
        ("遺伝子発現", "dnaからタンパク質", "DNAからRNA", "gene expression", "transcription", "translation"),
        "遺伝子発現では、DNAの情報が転写によってRNAへ写され、タンパク質を作る遺伝子では翻訳によってアミノ酸配列へ変換されます。",
        (
            "転写ではDNAの一方の鎖を鋳型としてRNAが合成されます。",
            "翻訳ではリボソームがmRNAのコドンを読み、対応するアミノ酸をつないでタンパク質を合成します。",
            "発現量は転写制御、RNA処理、分解、翻訳効率など複数段階で調節されます。",
        ),
        ("すべてのRNAがタンパク質へ翻訳されるわけではなく、機能性RNAとして働くものもあります。",),
    ),
    Concept(
        "acid_base",
        ("酸と塩基", "酸塩基", "acid base", "酸", "塩基"),
        "ブレンステッド・ローリーの定義では、酸はプロトンを与える物質、塩基はプロトンを受け取る物質です。",
        (
            "酸塩基反応ではプロトン移動が起こり、酸と共役塩基、塩基と共役酸の組ができます。",
            "水溶液のpHは水素イオン活量に関係し、希薄な理想近似では pH≈-log10[H+] と扱えます。",
        ),
        ("ルイス酸塩基の定義では電子対の授受で捉えるため、ブレンステッドの定義より広い範囲を扱えます。",),
    ),
    Concept(
        "algorithm_complexity",
        ("計算量", "アルゴリズム計算量", "big o", "big-o", "complexity"),
        "計算量は、入力サイズが大きくなったときに処理時間や使用メモリがどう増えるかを表す尺度です。",
        (
            "Big-O記法は主に漸近的な増え方の上界を表し、定数倍や低次項を捨てて成長率を比較します。",
            "同じBig-Oでも実測速度は実装、定数係数、キャッシュ、入力分布などで変わります。",
        ),
        ("漸近計算量だけで小規模入力の実性能まで決まるわけではありません。",),
    ),
)


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(
        r"[\\s\\-‐-–—_・･、。，．,:：;；!?！？'\"「」『』()（）\\[\\]{}]+",
        "",
        value,
    )


def _topic_score(concept: Concept, text: str) -> float:
    n = _norm(text)
    score = 0.0
    for alias in concept.aliases:
        a = _norm(alias)
        if not a:
            continue
        if a in n:
            score += 4.0 + min(2.0, len(a) / 8.0)
    return score


def is_context_only_followup(text: str) -> bool:
    """Return True only when the turn depends on prior context for its subject.

    This is a language-structure gate, not a topic list. A clarification cue is
    allowed to borrow history only when removing generic reference/request
    framing leaves no substantive current-turn subject behind.
    """
    value = unicodedata.normalize("NFKC", str(text or "")).strip()
    if not value:
        return False

    direct = re.fullmatch(
        r"(?:それ|これ|その点|この点|その話|この話|では|じゃあ|もう少し|詳しく)?"
        r"(?:について|に関して|は)?[？?。！!\\s]*",
        value,
        re.I,
    )
    if direct:
        return True

    cue = re.compile(
        r"(どういうこと|どういう意味|何を意味|つまり|要するに|簡単に|かみ砕|もう一度|もう少し|"
        r"(?:わか|分か|理解)(?:ります|できます|できる).*(?:か|？|\\?))",
        re.I,
    )
    if not cue.search(value):
        return False

    residual = cue.sub(" ", value)
    residual = re.sub(
        r"(?:それ|これ|その点|この点|その話|この話|この件|では|じゃあ|"
        r"について|に関して|とは|って|教えて|説明して|ください|下さい|お願いします|"
        r"です|ます|でした|ました|は|を|の|に|で|か)+",
        " ",
        residual,
        flags=re.I,
    )
    residual = re.sub(r"[\\s？?。！!、,・:：;；「」『』()（）]+", "", residual)
    return not residual


class ReflectiveConversationOrgan:
    """Local knowledge-grounded conversational reasoning.

    The organ is deliberately broader than exact fact lookup but remains
    fail-closed. It can elaborate an explicit local concept, resolve a recent
    topic, compare two known concepts, or reason structurally from a premise
    supplied by the user. It does not invent external facts for unknown topics.
    """

    FOLLOWUP = re.compile(r"^(?:それ|これは|その点|では|じゃあ|もう少し|詳しく)?(?:について|に関して|は)?[？?。\s]*$")
    CONTEXTUAL_FOLLOWUP = re.compile(
        r"(どういうこと|どういう意味|何を意味|つまり|要するに|"
        r"簡単に|かみ砕|もう一度|もう少し|"
        r"(?:わか|分か|理解)(?:ります|できます|できる).*(?:か|？|\?))",
        re.I,
    )
    PREMISE_REASONING = re.compile(
        r"(どう思う|どう考える|妥当|仮説|もし|仮に|とすると|としたら|"
        r"という見方|という考え|捉えると|観点|本質|前提|何が欠損|"
        r"成り立つ|あり得る|可能性)",
        re.I,
    )

    def _rank(self, text: str) -> list[tuple[float, Concept]]:
        return sorted(
            ((_topic_score(c, text), c) for c in CONCEPTS),
            key=lambda x: (-x[0], x[1].concept_id),
        )

    def _match(self, text: str) -> tuple[Concept | None, float]:
        scored = self._rank(text)
        if not scored or scored[0][0] <= 0:
            return None, 0.0
        return scored[0][1], scored[0][0]

    def _from_history(self, history: list[Mapping]) -> Concept | None:
        for row in reversed(history[-12:]):
            value = str(row.get("text", "")).strip()
            if not value:
                continue
            concept, score = self._match(value)
            if concept is not None and score > 0:
                return concept
        return None

    @staticmethod
    def _last_user_premise(history: list[Mapping]) -> str:
        for row in reversed(history[-12:]):
            if row.get("role") != "user":
                continue
            value = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
            if value:
                return value[:360]
        return ""

    @staticmethod
    def _render_premise_reasoning(claim: str) -> str:
        claim = re.sub(r"\s+", " ", str(claim or "")).strip()
        if len(claim) > 220:
            claim = claim[:219] + "…"
        return (
            f"その内容は、仮説・前提として考えることができます。対象の主張は「{claim}」です。"
            "まず前提と結論を分け、前提から何が実際に予測されるかを出します。"
            "次に、同じ結果を説明できる別の仮説と、主張が崩れる反例を並べます。"
            "最後に、どの観測や実験なら仮説同士を区別できるかを見ると、"
            "単なる賛否ではなく検証可能な議論になります。"
            "外部知識が必要な部分は、ローカル根拠がない限り事実として補いません。"
        )

    @staticmethod
    def _question_mode(text: str) -> str:
        t = str(text or "")
        if re.search(r"(なぜ|どうして|理由|原因|why)", t, re.I):
            return "why"
        if re.search(r"(どういうこと|どういう意味|つまり|要するに|簡単に|かみ砕)", t, re.I):
            return "clarify"
        if re.search(r"(どう動|仕組み|メカニズム|どのよう|どういう|how)", t, re.I):
            return "how"
        if re.search(r"(違い|比較|比べ|difference|compare)", t, re.I):
            return "compare"
        if re.search(r"(詳しく|深く|もう少し|掘り下げ)", t):
            return "deep"
        return "overview"

    @staticmethod
    def _join_sentences(rows: tuple[str, ...], limit: int) -> str:
        return "".join(rows[:limit])

    @staticmethod
    def _render_compare(a: Concept, b: Concept) -> str:
        a_mech = a.mechanisms[0] if a.mechanisms else a.summary
        b_mech = b.mechanisms[0] if b.mechanisms else b.summary
        return (
            f"{a.summary}{b.summary}"
            f"違いを短く言うと、前者は「{a_mech}」が中心で、"
            f"後者は「{b_mech}」が中心です。"
            "両者は独立とは限らず、同じ現象の中で同時に働く場合があります。"
        )

    def _render(self, concept: Concept, text: str, *, followup: bool) -> str:
        mode = self._question_mode(text)
        if mode == "why":
            body = self._join_sentences(concept.mechanisms, 3)
            reply = concept.summary + body
        elif mode == "clarify":
            if concept.plain:
                reply = concept.plain
            else:
                reply = "要するに、" + concept.summary + self._join_sentences(concept.mechanisms, 1)
        elif mode == "how":
            body = self._join_sentences(concept.mechanisms, 4)
            reply = concept.summary + body
        elif mode == "deep":
            body = self._join_sentences(concept.mechanisms, 4)
            caveat = self._join_sentences(concept.boundaries, 2)
            reply = concept.summary + body + caveat
        else:
            body = self._join_sentences(concept.mechanisms, 3)
            caveat = self._join_sentences(concept.boundaries, 1)
            reply = concept.summary + body + caveat

        if followup:
            reply = "その話題の続きとして説明します。" + reply
        return reply

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        t = str(text or "").strip()
        if not t:
            return None

        ranked = self._rank(t)
        concept = ranked[0][1] if ranked and ranked[0][0] > 0 else None
        score = ranked[0][0] if ranked and ranked[0][0] > 0 else 0.0
        followup = False
        contextual_followup = bool(self.CONTEXTUAL_FOLLOWUP.search(t))
        context_only_followup = is_context_only_followup(t)
        if concept is None and context_only_followup:
            concept = self._from_history(history)
            followup = concept is not None
            score = 2.5 if followup else 0.0

        if concept is None:
            premise_trigger = bool(self.PREMISE_REASONING.search(t))
            short_opinion = bool(re.fullmatch(r"(?:それ|これ|その話)?(?:は)?どう(?:思う|考える)[？?。\s]*", t))
            claim = t
            if short_opinion:
                claim = self._last_user_premise(history)
            if premise_trigger and claim:
                return {
                    "ok": True,
                    "reply": self._render_premise_reasoning(claim),
                    "confidence": 0.82,
                    "needs_teacher": False,
                    "local": True,
                    "reflective_reasoning": True,
                    "grounded": True,
                    "grounding": "user-premise",
                    "topic_id": "user-premise",
                    "evidence_ids": ["user-premise"],
                    "reasoning_mode": "premise",
                    "followup_resolved": bool(short_opinion),
                    "related_topics": [],
                }
            return None

        mode = self._question_mode(t)
        second = None
        if mode == "compare":
            for s, candidate in ranked[1:]:
                if s > 0 and candidate.concept_id != concept.concept_id:
                    second = candidate
                    break

        if second is not None:
            reply = self._render_compare(concept, second)
            evidence_ids = [concept.concept_id, second.concept_id]
        else:
            reply = self._render(concept, t, followup=followup)
            evidence_ids = [concept.concept_id]

        return {
            "ok": True,
            "reply": reply,
            "confidence": 0.94 if score >= 4.0 else 0.84,
            "needs_teacher": False,
            "local": True,
            "reflective_reasoning": True,
            "grounded": True,
            "topic_id": concept.concept_id,
            "evidence_ids": evidence_ids,
            "reasoning_mode": mode,
            "followup_resolved": followup,
            "contextual_followup": bool(followup and contextual_followup and context_only_followup),
            "related_topics": list(concept.related),
        }
