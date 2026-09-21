from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Sequence


_KIND_TERMS = {
    "human": r"(?:人|人物|人間|男性|女性|男の人|女の人|person|people|human|man|woman)",
    "dog": r"(?:犬|わんこ|ワンコ|ビーグル|dog|beagle|puppy)",
    "bird": r"(?:鳥|小鳥|野鳥|bird|sparrow|pigeon|eagle)",
    "cat": r"(?:猫|ネコ|ねこ|cat|kitten)",
    "horse": r"(?:馬|ウマ|horse)",
    "car": r"(?:車|自動車|乗用車|car|automobile|vehicle)",
}

_JA_NUMBERS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

_COLORS = (
    ("white", r"白い|白の|白色|white"),
    ("black", r"黒い|黒の|黒色|black"),
    ("red", r"赤い|赤の|赤色|red"),
    ("blue", r"青い|青の|青色|blue"),
    ("brown", r"茶色|茶の|brown"),
    ("gray", r"灰色|グレー|gray|grey"),
)

_STATES = {
    "human": (
        ("sitting", r"座って|座る|sitting|seated"),
        ("walking", r"歩いて|歩く|walking"),
        ("standing", r"立って|立つ|standing"),
    ),
    "dog": (
        ("sitting", r"座って|座る|sitting"),
        ("standing", r"立って|立つ|standing"),
        ("running", r"走って|走る|running"),
    ),
    "bird": (
        ("flying", r"飛んで|飛ぶ|飛行|flying"),
        ("perched", r"止まって|とまって|perched"),
    ),
    "cat": (
        ("sitting", r"座って|座る|sitting"),
        ("standing", r"立って|立つ|standing"),
    ),
    "horse": (
        ("running", r"走って|走る|running"),
        ("standing", r"立って|立つ|standing"),
    ),
    "car": (
        ("moving", r"走って|走行|moving|driving"),
        ("parked", r"駐車|停車|parked"),
    ),
}


@dataclass(frozen=True)
class SceneNode:
    node_id: str
    kind: str
    index: int
    attributes: tuple[tuple[str, str], ...] = ()
    state: str = "default"

    def attr_dict(self) -> dict[str, str]:
        return dict(self.attributes)


@dataclass(frozen=True)
class SceneRelation:
    source_kind: str
    relation: str
    target_kind: str

    def key(self) -> str:
        return f"{self.source_kind}:{self.relation}:{self.target_kind}"


@dataclass(frozen=True)
class SceneGraph2:
    nodes: tuple[SceneNode, ...]
    relations: tuple[SceneRelation, ...]
    forbidden_kinds: tuple[str, ...]
    requested_styles: tuple[str, ...]
    viewpoint: str
    centered_subjects: bool
    source_text: str

    @property
    def required_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for node in self.nodes:
            out[node.kind] = out.get(node.kind, 0) + 1
        return out

    @property
    def required_objects(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(node.kind for node in self.nodes))


def _count_value(raw: str | None) -> int:
    if not raw:
        return 1
    raw = raw.strip()
    if raw.isdigit():
        return max(1, min(8, int(raw)))
    return _JA_NUMBERS.get(raw, 1)


def _negative_kind(text: str, kind: str) -> bool:
    term = _KIND_TERMS[kind]
    patterns = (
        rf"{term}\s*(?:は|を)?\s*(?:入れない|含めない|出さない|描かない|不要|なし)",
        rf"(?:なし|除外)\s*(?:の)?\s*{term}",
        rf"\b(?:without|no)\s+{term}\b",
    )
    return any(re.search(p, text, re.I) for p in patterns)


def _kind_count(text: str, kind: str) -> int:
    term = _KIND_TERMS[kind]
    number = r"(\d+|[一二三四五六七八九十])"
    patterns = (
        rf"{number}\s*(?:人|匹|羽|頭|台|個)?\s*(?:の)?\s*{term}",
        rf"{term}\s*(?:が|は|を)?\s*{number}\s*(?:人|匹|羽|頭|台|個)?",
    )
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return _count_value(m.group(1))
    return 1


def _kind_context(text: str, kind: str) -> str:
    term = _KIND_TERMS[kind]
    m = re.search(term, text, re.I)
    if not m:
        return text
    a = max(0, m.start() - 26)
    b = min(len(text), m.end() + 30)
    return text[a:b]


def _attributes_and_state(text: str, kind: str) -> tuple[tuple[tuple[str, str], ...], str]:
    ctx = _kind_context(text, kind)
    attrs: list[tuple[str, str]] = []
    for value, pattern in _COLORS:
        if re.search(pattern, ctx, re.I):
            attrs.append(("color", value))
            break
    state = "default"
    for value, pattern in _STATES.get(kind, ()):
        if re.search(pattern, ctx, re.I):
            state = value
            break
    return tuple(attrs), state


def _relation_patterns() -> tuple[tuple[str, str, str, str], ...]:
    # (source kind, relation, target kind, regex-template marker) is assembled
    # dynamically because kind terms contain multiple Japanese/English aliases.
    out = []
    kinds = tuple(_KIND_TERMS)
    for a in kinds:
        for b in kinds:
            if a == b:
                continue
            ta, tb = _KIND_TERMS[a], _KIND_TERMS[b]
            out.extend((
                (a, "above", b, rf"{ta}.*?{tb}\s*の\s*上|{tb}\s*の\s*上(?:に|を).*?{ta}"),
                (a, "below", b, rf"{ta}.*?{tb}\s*の\s*下|{tb}\s*の\s*下(?:に|を).*?{ta}"),
                (a, "left_of", b, rf"{ta}.*?{tb}\s*の\s*左|{tb}\s*の\s*左(?:に|を).*?{ta}"),
                (a, "right_of", b, rf"{ta}.*?{tb}\s*の\s*右|{tb}\s*の\s*右(?:に|を).*?{ta}"),
                (a, "next_to", b, rf"{ta}.*?{tb}\s*の\s*(?:横|隣)|{tb}\s*の\s*(?:横|隣)(?:に|を).*?{ta}"),
                (a, "looking_at", b, rf"{ta}\s*(?:が|は).*?{tb}\s*を\s*(?:見て|見る|見つめ)"),
            ))
    return tuple(out)


def _relations(text: str, forbidden: set[str]) -> tuple[SceneRelation, ...]:
    seen: set[str] = set()
    out: list[SceneRelation] = []
    for source, relation, target, pattern in _relation_patterns():
        if source in forbidden or target in forbidden:
            continue
        if re.search(pattern, text, re.I):
            item = SceneRelation(source, relation, target)
            if item.key() not in seen:
                seen.add(item.key())
                out.append(item)
    return tuple(out)


def _viewpoint(text: str) -> str:
    if re.search(r"側面|横から|横向き|side view|profile", text, re.I):
        return "side"
    if re.search(r"背面|後ろから|back view|rear view", text, re.I):
        return "back"
    if re.search(r"斜め|3/4|three[- ]quarter|oblique", text, re.I):
        return "oblique"
    if re.search(r"正面|front view|from the front", text, re.I):
        return "front"
    return "front"


def _styles(text: str) -> tuple[str, ...]:
    styles: list[str] = []
    if re.search(r"写真風|写真のよう|フォトリアル|写実|実写|photo|photoreal", text, re.I):
        styles.append("photorealistic")
    if re.search(r"イラスト|漫画|アニメ|illustration|anime|cartoon", text, re.I):
        styles.append("illustration")
    if not styles:
        styles.append("geometric-3d")
    return tuple(styles)


def parse_scene_graph(prompt: str, constraints: Sequence[str] = ()) -> SceneGraph2:
    text = "\n".join([str(prompt or ""), *(str(x or "") for x in constraints)])
    forbidden = {kind for kind in _KIND_TERMS if _negative_kind(text, kind)}

    nodes: list[SceneNode] = []
    for kind, term in _KIND_TERMS.items():
        if kind in forbidden or not re.search(term, text, re.I):
            continue
        count = _kind_count(text, kind)
        attrs, state = _attributes_and_state(text, kind)
        for index in range(1, count + 1):
            nodes.append(SceneNode(
                node_id=f"{kind}_{index}",
                kind=kind,
                index=index,
                attributes=attrs,
                state=state,
            ))

    return SceneGraph2(
        nodes=tuple(nodes),
        relations=_relations(text, forbidden),
        forbidden_kinds=tuple(sorted(forbidden)),
        requested_styles=_styles(text),
        viewpoint=_viewpoint(text),
        centered_subjects=bool(re.search(r"中央|中心|センター|center", text, re.I)),
        source_text=text,
    )
