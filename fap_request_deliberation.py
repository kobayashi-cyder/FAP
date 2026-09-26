from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any, Mapping, Sequence


_SPLIT = re.compile(r"[\n。！？!?;；]+")
_CONSTRAINT = re.compile(
    r"(?:必ず|絶対|のみ|だけ|以内|以下|以上|未満|超え|禁止|しないで|使わない|必要|必須|"
    r"must\b|only\b|without\b|do not\b|don't\b|never\b|at most\b|at least\b)",
    re.I,
)
_COUNTEREXAMPLE = re.compile(
    r"(?:反例|例外|反証|counterexample|falsif|always\b|never\b|すべて|全て|必ず|絶対)",
    re.I,
)
_VERIFY = re.compile(
    r"(?:検証|確認|証明|根拠|出典|正しい|矛盾|整合|verify|validation|prove|evidence|source|citation|consistent)",
    re.I,
)
_CORRECTION = re.compile(
    r"(?:違う|誤り|間違|修正|訂正|やり直|再検討|前の回答|さっきの回答|"
    r"wrong\b|incorrect\b|fix\b|correct\b|revise\b|reconsider\b)",
    re.I,
)
_CODE = re.compile(
    r"(?:python|c\+\+|\bc\b|java|kotlin|javascript|typescript|コード|実装|関数|プログラム|script|repository|repo|git|github)",
    re.I,
)
_CODE_ACTION = re.compile(
    r"(?:作って|作成|生成|書いて|実装|構築|修正|更新|変更|追加|削除|"
    r"build\b|create\b|make\b|implement\b|write\b|fix\b|update\b|change\b|add\b|remove\b)",
    re.I,
)
_MATH = re.compile(
    r"(?:計算|方程式|数式|微分|積分|確率|行列|ベクトル|証明|"
    r"calculate|compute|equation|algebra|derivative|integral|probability|matrix|vector)",
    re.I,
)
_SCIENCE = re.compile(
    r"(?:物理|化学|生物|力学|電磁|量子|熱力学|相対論|"
    r"physics|chemistry|biology|mechanics|quantum|thermodynamics|relativity)",
    re.I,
)
_CAUSAL = re.compile(
    r"(?:なぜ|どうして|原因|因果|影響|仕組|機構|why\b|cause|causal|effect|mechanism)",
    re.I,
)
_FACTUAL = re.compile(
    r"(?:いつ|誰|どこ|何年|何月|何日|価格|仕様|定義|"
    r"when\b|who\b|where\b|price\b|specification|define\b|definition)",
    re.I,
)
_PROFILE = re.compile(
    r"(?:あなたは|fapは|できること|機能|能力|version|バージョン|capabilit|status)",
    re.I,
)
_MULTI_STEP = re.compile(
    r"(?:まず|次に|その後|最後に|手順|段階|比較|それぞれ|"
    r"first\b|then\b|after that|finally\b|steps?\b|compare\b|each\b)",
    re.I,
)


def _clip(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(out):
        return default
    return max(0.0, min(1.0, out))


@dataclass(frozen=True)
class RequestDeliberationSignals:
    contract: str
    intent_count: int
    constraint_count: int
    counterexample: bool
    verification_pressure: float
    history_pressure: float
    correction_requested: bool
    task_family: str
    task_form: str
    required_capabilities: tuple[str, ...]
    failure_classes: tuple[str, ...]
    pressure_hint: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def routing_metadata(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.task_family:
            out["task_family"] = self.task_family
        if self.task_form:
            out["task_form"] = self.task_form
        if self.required_capabilities:
            out["required_capabilities"] = self.required_capabilities
        if self.failure_classes:
            out["failure_classes"] = self.failure_classes
        if self.verification_pressure > 0.0:
            out["uncertainty"] = self.verification_pressure
        return out


def _history_pressure(history: Sequence[Mapping[str, Any]]) -> float:
    rows = list(history)[-48:]
    if not rows:
        return 0.0
    turn_pressure = min(1.0, len(rows) / 32.0)
    corpus = " ".join(
        str(row.get("text") or row.get("content") or "")
        for row in rows[-12:]
        if isinstance(row, Mapping)
    )
    correction = 1.0 if _CORRECTION.search(corpus) else 0.0
    return _clip(0.72 * turn_pressure + 0.28 * correction)


def _intent_count(text: str) -> int:
    value = str(text or "").strip()
    if not value:
        return 0
    segments = [x.strip() for x in _SPLIT.split(value) if len(x.strip()) >= 2]
    segment_count = max(1, len(segments))

    connector_hits = len(
        re.findall(
            r"(?:さらに|加えて|それと|および|かつ|また|その上|"
            r"and\b|also\b|plus\b|additionally\b|then\b)",
            value,
            flags=re.I,
        )
    )
    explicit_questions = value.count("?") + value.count("？")
    return max(
        1,
        min(
            16,
            segment_count
            + min(4, connector_hits)
            + min(3, max(0, explicit_questions - 1)),
        ),
    )


def _classify(text: str, intent_count: int) -> tuple[str, str, tuple[str, ...]]:
    value = str(text or "")
    code = bool(_CODE.search(value))
    code_action = code and bool(_CODE_ACTION.search(value))
    math_hit = bool(_MATH.search(value))
    science = bool(_SCIENCE.search(value))
    causal = bool(_CAUSAL.search(value))
    factual = bool(_FACTUAL.search(value))
    profile = bool(_PROFILE.search(value))

    if profile:
        return "conversation", "factual", ("self_profile", "conversation")
    if code:
        form = "repository_change" if code_action else ("multi_step" if intent_count >= 2 else "reading")
        return "coding", form, ("coding", "verification") if code_action else ("coding",)
    if math_hit:
        form = "multi_step" if intent_count >= 2 or _MULTI_STEP.search(value) else "symbolic"
        return "math", form, ("logic", "derivation", "verification")
    if science:
        form = "multi_step" if intent_count >= 2 or causal else "factual"
        return "science", form, ("reasoning", "verification") if causal else ("facts", "verification")
    if factual:
        return "general", "factual", ("facts", "verification")
    if causal:
        return "general", "multi_step", ("reasoning", "verification")
    if intent_count >= 2:
        return "general", "multi_step", ("reasoning",)
    return "general", "", ()


def analyze_request(
    text: str,
    history: Sequence[Mapping[str, Any]] = (),
) -> RequestDeliberationSignals:
    value = str(text or "").strip()
    intents = _intent_count(value)
    segments = [x.strip() for x in _SPLIT.split(value) if x.strip()]
    constraints = sum(1 for x in segments if _CONSTRAINT.search(x))
    counterexample = bool(_COUNTEREXAMPLE.search(value))
    verification_cue = bool(_VERIFY.search(value))
    correction = bool(_CORRECTION.search(value))
    hist_pressure = _history_pressure(history)

    verification_pressure = _clip(
        0.18 * min(1.0, constraints / 3.0)
        + 0.24 * float(counterexample)
        + 0.26 * float(verification_cue)
        + 0.20 * float(correction)
        + 0.12 * min(1.0, max(0, intents - 1) / 5.0)
    )

    task_family, task_form, capabilities = _classify(value, intents)
    failures: list[str] = []
    if correction:
        failures.extend(("verification", "repair"))
    elif counterexample or verification_cue:
        failures.append("verification")

    structural_pressure = min(1.0, max(0, intents - 1) / 7.0)
    constraint_pressure = min(1.0, constraints / 4.0)
    pressure_hint = _clip(
        0.34 * structural_pressure
        + 0.22 * constraint_pressure
        + 0.26 * verification_pressure
        + 0.18 * hist_pressure
    )

    return RequestDeliberationSignals(
        contract="fap.request.deliberation.v1",
        intent_count=intents,
        constraint_count=min(16, constraints),
        counterexample=counterexample,
        verification_pressure=verification_pressure,
        history_pressure=hist_pressure,
        correction_requested=correction,
        task_family=task_family,
        task_form=task_form,
        required_capabilities=tuple(dict.fromkeys(capabilities)),
        failure_classes=tuple(dict.fromkeys(failures)),
        pressure_hint=pressure_hint,
    )
